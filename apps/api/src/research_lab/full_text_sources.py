from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeGuard, cast
from urllib.parse import urlparse

import httpx
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from research_lab.config import Settings
from research_lab.models import FullTextSourceAttempt, Paper

# Import resolvers for registration
try:
    from research_lab.resolvers.libgen import LibGenResult
    from research_lab.resolvers.sci_hub import SciHubResult

    HAS_RESOLVERS = True
except ImportError:
    SciHubResult = None  # type: ignore[assignment]
    LibGenResult = None  # type: ignore[assignment]
    HAS_RESOLVERS = False


def convert_resolver_result_to_candidate(result: Any) -> OpenAccessPdfCandidate | None:
    """Convert resolver result (SciHubResult or LibGenResult) to OpenAccessPdfCandidate.

    Args:
        result: SciHubResult or LibGenResult from resolvers

    Returns:
        OpenAccessPdfCandidate or None if no PDF URL found
    """
    if not hasattr(result, "pdf_url") or not result.pdf_url:
        return None

    # Handle SciHubResult
    if hasattr(result, "source_kind") and "sci_hub" in str(
        getattr(result, "source_kind", "")
    ):
        return OpenAccessPdfCandidate(
            url=result.pdf_url,
            source_kind=getattr(result, "source_kind", "sci_hub_pdf"),
            license=None,
            source_record_id=str(getattr(result, "doi", None) or getattr(result, "pmid", None)),
            metadata={
                "doi": getattr(result, "doi", None),
                "pmid": getattr(result, "pmid", None),
                "domain_used": getattr(result, "domain_used", None),
                "error": getattr(result, "error", None),
            },
        )

    # Handle LibGenResult
    if hasattr(result, "source_kind") and "libgen" in str(getattr(result, "source_kind", "")):
        return OpenAccessPdfCandidate(
            url=result.pdf_url,
            source_kind=getattr(result, "source_kind", "libgen_pdf"),
            license=None,
            source_record_id=str(
                getattr(result, "identifier", None)
                or getattr(result, "doi", None)
                or getattr(result, "isbn", None)
            ),
            metadata={
                "identifier": getattr(result, "identifier", None),
                "doi": getattr(result, "doi", None),
                "isbn": getattr(result, "isbn", None),
                "error": getattr(result, "error", None),
            },
        )

    return None


@dataclass(frozen=True)
class OpenAccessPdfCandidate:
    url: str
    license: str | None
    source_kind: str
    media_type: str = "pdf"
    source_record_id: str | None = None
    request_params: tuple[tuple[str, str], ...] = field(default=(), repr=False, compare=False)
    request_headers: tuple[tuple[str, str], ...] = field(default=(), repr=False, compare=False)
    metadata: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @property
    def pdf_url(self) -> str:
        """Compatibility alias for provider adapters that return `pdf_url`."""
        return self.url

    @property
    def domain(self) -> str | None:
        hostname = urlparse(self.url).hostname
        return hostname.lower() if hostname else None


@dataclass(frozen=True)
class SourceDomainHealth:
    attempts: int
    successes: int

    @property
    def success_rate(self) -> float:
        return self.successes / self.attempts if self.attempts else 0.0

    @property
    def quality_score(self) -> float:
        # A small Beta prior keeps one-off successes/failures from dominating
        # routing while allowing repeated publisher behavior to matter quickly.
        return (self.successes + 2) / (self.attempts + 4)

    @property
    def low_yield(self) -> bool:
        return self.attempts >= 3 and self.success_rate <= 0.25


class FullTextSourceResolver(Protocol):
    def resolve(
        self,
        paper: Paper,
        *,
        exclude_urls: set[str] | None = None,
    ) -> list[OpenAccessPdfCandidate]: ...


class OpenAlexSourceResolver:
    """Refresh rights-safe OpenAlex locations without bypassing publisher access controls."""

    def __init__(self, settings: Settings, client: httpx.Client) -> None:
        self.settings = settings
        self.client = client

    def resolve(self, paper: Paper, *, exclude_urls: set[str] | None = None) -> list[OpenAccessPdfCandidate]:
        excluded = exclude_urls or set()
        openalex_id = paper.openalex_id
        if not openalex_id and paper.primary_source == "openalex" and paper.source_record_id.startswith("W"):
            openalex_id = paper.source_record_id
        if not openalex_id:
            return []
        params: dict[str, str] = {}
        if self.settings.openalex_api_key:
            params["api_key"] = self.settings.openalex_api_key
        params["select"] = "best_oa_location,primary_location,locations,has_content,content_urls"
        response = self.client.get(
            f"{self.settings.openalex_base_url.rstrip('/')}/works/{openalex_id}",
            params=params,
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            return []

        raw_locations: list[tuple[str, dict[str, Any]]] = []
        candidates: list[OpenAccessPdfCandidate] = []
        content_urls = payload.get("content_urls")
        has_content = payload.get("has_content")
        if (
            self.settings.openalex_api_key
            and isinstance(has_content, dict)
            and has_content.get("pdf") is True
            and isinstance(content_urls, dict)
        ):
            content_pdf = content_urls.get("pdf")
            if isinstance(content_pdf, str) and content_pdf.startswith(("http://", "https://")):
                raw_locations.append(
                    (
                        "openalex_content_pdf",
                        {
                            "is_oa": True,
                            "pdf_url": content_pdf,
                            "license": paper.license,
                            "_request_params": (("api_key", self.settings.openalex_api_key),),
                        },
                    )
                )
        if (
            self.settings.openalex_api_key
            and isinstance(has_content, dict)
            and has_content.get("grobid_xml") is True
            and isinstance(content_urls, dict)
        ):
            content_xml = content_urls.get("grobid_xml")
            if isinstance(content_xml, str) and content_xml.startswith(("http://", "https://")):
                candidates.append(
                    OpenAccessPdfCandidate(
                        url=content_xml,
                        license=paper.license,
                        source_kind="openalex_content_grobid_xml",
                        media_type="xml",
                        source_record_id=openalex_id,
                        request_params=(("api_key", self.settings.openalex_api_key),),
                    )
                )
        best = payload.get("best_oa_location")
        primary = payload.get("primary_location")
        if isinstance(best, dict):
            raw_locations.append(("openalex_best_oa_location", best))
        if isinstance(primary, dict):
            raw_locations.append(("openalex_primary_location", primary))
        locations = payload.get("locations")
        if isinstance(locations, list):
            raw_locations.extend(
                ("openalex_location", location)
                for location in locations
                if isinstance(location, dict)
            )

        seen: set[str] = set()
        for source_kind, location in raw_locations:
            url = location.get("pdf_url")
            if location.get("is_oa") is not True or not isinstance(url, str) or not url.startswith(("http://", "https://")):
                continue
            if url in excluded or url in seen:
                continue
            seen.add(url)
            license_label = location.get("license")
            raw_request_params = location.get("_request_params")
            request_params = (
                tuple(
                    (str(key), str(value))
                    for key, value in raw_request_params
                    if isinstance(key, str) and isinstance(value, str)
                )
                if isinstance(raw_request_params, tuple)
                else ()
            )
            candidates.append(
                OpenAccessPdfCandidate(
                    url=url,
                    license=license_label if isinstance(license_label, str) else paper.license,
                    source_kind=source_kind,
                    media_type="pdf",
                    source_record_id=openalex_id,
                    request_params=request_params,
                )
            )
        return candidates


# Backwards-compatible import for callers and tests written before the resolver
# was given its provider-specific name.
OpenAccessSourceResolver = OpenAlexSourceResolver


class EuropePmcSourceResolver:
    """Resolve DOI-matched Europe PMC Open Access full text through the REST API."""

    search_url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    full_text_base_url = "https://www.ebi.ac.uk/europepmc/webservices/rest"

    def __init__(self, client: httpx.Client) -> None:
        self.client = client

    def resolve(
        self,
        paper: Paper,
        *,
        exclude_urls: set[str] | None = None,
    ) -> list[OpenAccessPdfCandidate]:
        if not paper.doi:
            return []
        excluded = exclude_urls or set()
        response = self.client.get(
            self.search_url,
            params={
                "query": f'DOI:{paper.doi} AND OPEN_ACCESS:Y',
                "format": "json",
                "resultType": "core",
                "pageSize": "1",
            },
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            return []
        result_list = payload.get("resultList")
        if not isinstance(result_list, dict):
            return []
        results = result_list.get("result")
        if not isinstance(results, list) or not results or not isinstance(results[0], dict):
            return []
        record = results[0]
        if record.get("isOpenAccess") != "Y":
            return []
        pmcid = record.get("pmcid")
        if not isinstance(pmcid, str) or not pmcid.startswith("PMC"):
            return []
        url = f"{self.full_text_base_url}/{pmcid}/fullTextXML"
        if url in excluded:
            return []
        raw_license = record.get("license")
        license_label = raw_license if isinstance(raw_license, str) else paper.license
        return [
            OpenAccessPdfCandidate(
                url=url,
                license=license_label,
                source_kind="europe_pmc_oa_xml",
                media_type="xml",
                source_record_id=pmcid,
            )
        ]


class ArxivResolver:
    """Resolve a known arXiv identifier to the repository's public PDF endpoint."""

    def resolve(
        self,
        paper: Paper,
        *,
        exclude_urls: set[str] | None = None,
    ) -> list[OpenAccessPdfCandidate]:
        if not paper.arxiv_id:
            return []
        url = f"https://arxiv.org/pdf/{paper.arxiv_id}"
        if url in (exclude_urls or set()):
            return []
        return [
            OpenAccessPdfCandidate(
                url=url,
                license=paper.license,
                source_kind="arxiv_pdf",
                media_type="pdf",
                source_record_id=paper.arxiv_id,
            )
        ]


class UnpaywallSourceResolver:
    """Resolve DOI-indexed open copies through the official Unpaywall v2 API."""

    def __init__(self, settings: Settings, client: httpx.Client) -> None:
        self.client = client
        self.base_url = settings.unpaywall_base_url.rstrip("/")
        self.email = settings.unpaywall_email or settings.crossref_mailto

    def resolve(
        self,
        paper: Paper,
        *,
        exclude_urls: set[str] | None = None,
    ) -> list[OpenAccessPdfCandidate]:
        if not paper.doi or not self.email:
            return []
        response = self.client.get(
            f"{self.base_url}/{paper.doi}",
            params={"email": self.email},
            headers={"Accept": "application/json"},
        )
        if response.status_code == 404:
            return []
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or payload.get("is_oa") is not True:
            return []

        locations: list[tuple[str, dict[str, Any]]] = []
        best = payload.get("best_oa_location")
        if isinstance(best, dict):
            locations.append(("unpaywall_best_oa_pdf", best))
        raw_locations = payload.get("oa_locations")
        if isinstance(raw_locations, list):
            locations.extend(
                ("unpaywall_oa_pdf", location)
                for location in raw_locations
                if isinstance(location, dict)
            )

        excluded = exclude_urls or set()
        seen: set[str] = set()
        candidates: list[OpenAccessPdfCandidate] = []
        for source_kind, location in locations:
            url = location.get("url_for_pdf")
            if not _is_http_url(url) or url in excluded or url in seen:
                continue
            seen.add(url)
            raw_license = location.get("license")
            candidates.append(
                OpenAccessPdfCandidate(
                    url=url,
                    license=raw_license if isinstance(raw_license, str) else paper.license,
                    source_kind=source_kind,
                    source_record_id=paper.doi,
                )
            )
        return candidates


class CoreSourceResolver:
    """Resolve DOI-matched full text through the official CORE API v3."""

    def __init__(self, settings: Settings, client: httpx.Client) -> None:
        self.client = client
        self.base_url = settings.core_base_url.rstrip("/")
        self.api_key = settings.core_api_key

    def resolve(
        self,
        paper: Paper,
        *,
        exclude_urls: set[str] | None = None,
    ) -> list[OpenAccessPdfCandidate]:
        if not paper.doi or not self.api_key:
            return []
        headers = {"Accept": "application/json", "Authorization": f"Bearer {self.api_key}"}
        response = self.client.get(
            f"{self.base_url}/search/outputs/",
            params={"q": f'doi:"{paper.doi}"', "limit": "3"},
            headers=headers,
        )
        if response.status_code == 404:
            return []
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            return []
        results = payload.get("results")
        if not isinstance(results, list):
            return []

        normalized_doi = _normalize_doi(paper.doi)
        record = next(
            (
                item
                for item in results
                if isinstance(item, dict) and _normalize_doi(item.get("doi")) == normalized_doi
            ),
            None,
        )
        if record is None:
            return []
        core_id = record.get("id")
        if not isinstance(core_id, (int, str)):
            return []
        raw_license = record.get("license")
        license_label = raw_license if isinstance(raw_license, str) and raw_license else paper.license
        excluded = exclude_urls or set()
        candidates: list[OpenAccessPdfCandidate] = []
        seen: set[str] = set()

        preferred = record.get("downloadUrl")
        if _is_http_url(preferred):
            candidates.append(
                OpenAccessPdfCandidate(
                    url=preferred,
                    license=license_label,
                    source_kind="core_download_url_pdf",
                    source_record_id=str(core_id),
                )
            )
            seen.add(preferred)

        source_urls = record.get("sourceFulltextUrls")
        if isinstance(source_urls, list):
            for source_url in source_urls:
                if (
                    _is_http_url(source_url)
                    and _looks_like_pdf_url(source_url)
                    and source_url not in seen
                ):
                    candidates.append(
                        OpenAccessPdfCandidate(
                            url=source_url,
                            license=license_label,
                            source_kind="core_source_fulltext_pdf",
                            source_record_id=str(core_id),
                        )
                    )
                    seen.add(source_url)

        if record.get("fulltextStatus") == "enabled" or record.get("fullText"):
            api_download_url = f"{self.base_url}/outputs/{core_id}/download"
            if api_download_url not in seen:
                candidates.append(
                    OpenAccessPdfCandidate(
                        url=api_download_url,
                        license=license_label,
                        source_kind="core_api_download_pdf",
                        source_record_id=str(core_id),
                        request_headers=(("Authorization", f"Bearer {self.api_key}"),),
                    )
                )

        return [candidate for candidate in candidates if candidate.url not in excluded]


class PreprintSourceResolver:
    """Resolve bioRxiv, medRxiv, and ChemRxiv records through official APIs."""

    def __init__(self, settings: Settings, client: httpx.Client) -> None:
        self.client = client
        self.biorxiv_base_url = settings.biorxiv_api_base_url.rstrip("/")
        self.chemrxiv_base_url = settings.chemrxiv_api_base_url.rstrip("/")

    def resolve(
        self,
        paper: Paper,
        *,
        exclude_urls: set[str] | None = None,
    ) -> list[OpenAccessPdfCandidate]:
        doi = _normalize_doi(paper.doi)
        if doi is None:
            return []
        if doi.startswith("10.1101/"):
            return self._resolve_biorxiv_or_medrxiv(paper, doi, exclude_urls or set())
        if doi.startswith("10.26434/") and "chemrxiv" in doi:
            return self._resolve_chemrxiv(paper, doi, exclude_urls or set())
        return []

    def _resolve_biorxiv_or_medrxiv(
        self,
        paper: Paper,
        doi: str,
        excluded: set[str],
    ) -> list[OpenAccessPdfCandidate]:
        for server in ("biorxiv", "medrxiv"):
            response = self.client.get(
                f"{self.biorxiv_base_url}/details/{server}/{doi}/na/json",
                headers={"Accept": "application/json"},
            )
            if response.status_code == 404:
                continue
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                continue
            collection = payload.get("collection")
            if not isinstance(collection, list):
                continue
            records = [record for record in collection if isinstance(record, dict)]
            if not records:
                continue
            record = max(records, key=lambda item: _numeric_version(item.get("version")))
            source_server = str(record.get("server") or server).lower()
            raw_license = record.get("license")
            license_label = raw_license if isinstance(raw_license, str) else paper.license
            jats_url = record.get("jatsxml")
            candidates: list[OpenAccessPdfCandidate] = []
            if _is_http_url(jats_url) and jats_url not in excluded:
                candidates.append(
                    OpenAccessPdfCandidate(
                        url=jats_url,
                        license=license_label,
                        source_kind=f"{source_server}_jats_xml",
                        media_type="xml",
                        source_record_id=doi,
                    )
                )
                pdf_url = (
                    jats_url.removesuffix(".source.xml") + ".full.pdf"
                    if jats_url.endswith(".source.xml")
                    else None
                )
                if pdf_url and pdf_url not in excluded:
                    candidates.append(
                        OpenAccessPdfCandidate(
                            url=pdf_url,
                            license=license_label,
                            source_kind=f"{source_server}_pdf",
                            source_record_id=doi,
                        )
                    )
            return candidates
        return []

    def _resolve_chemrxiv(
        self,
        paper: Paper,
        doi: str,
        excluded: set[str],
    ) -> list[OpenAccessPdfCandidate]:
        response = self.client.get(
            f"{self.chemrxiv_base_url}/items/doi/{doi}",
            headers={"Accept": "application/json"},
        )
        if response.status_code in {404, 410}:
            return []
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            return []
        asset = payload.get("asset")
        if not isinstance(asset, dict) or asset.get("mimeType") != "application/pdf":
            return []
        original = asset.get("original")
        url = original.get("url") if isinstance(original, dict) else None
        if not _is_http_url(url) or url in excluded:
            return []
        raw_license = payload.get("license")
        license_label = raw_license.get("name") if isinstance(raw_license, dict) else None
        record_id = payload.get("id")
        return [
            OpenAccessPdfCandidate(
                url=url,
                license=license_label if isinstance(license_label, str) else paper.license,
                source_kind="chemrxiv_pdf",
                source_record_id=str(record_id) if record_id is not None else doi,
            )
        ]


def direct_repository_candidates(paper: Paper) -> list[OpenAccessPdfCandidate]:
    """Return deterministic public repository URLs already identified on the paper."""
    return ArxivResolver().resolve(paper)


def _is_http_url(value: object) -> TypeGuard[str]:
    return isinstance(value, str) and value.startswith(("http://", "https://"))


def _looks_like_pdf_url(value: str) -> bool:
    path = urlparse(value).path.lower()
    return path.endswith(".pdf") or "/pdf/" in path or "/download/" in path


def _normalize_doi(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :].strip()
    return normalized or None


def _numeric_version(value: object) -> int:
    try:
        return int(str(value))
    except ValueError:
        return 0


def source_domain_health(
    session: Session,
    domains: set[str],
) -> dict[str, SourceDomainHealth]:
    if not domains:
        return {}
    success = func.sum(case((FullTextSourceAttempt.status == "completed", 1), else_=0))
    rows = session.execute(
        select(
            FullTextSourceAttempt.domain,
            func.count(FullTextSourceAttempt.id),
            success,
        )
        .where(FullTextSourceAttempt.domain.in_(domains))
        .group_by(FullTextSourceAttempt.domain)
    ).all()
    return {
        str(domain): SourceDomainHealth(attempts=int(attempts), successes=int(successes or 0))
        for domain, attempts, successes in rows
        if domain is not None
    }


def should_refresh_before_direct_attempt(session: Session, candidate: OpenAccessPdfCandidate) -> bool:
    if candidate.domain is None:
        return False
    health = source_domain_health(session, {candidate.domain}).get(candidate.domain)
    return health.low_yield if health is not None else False


def rank_open_access_candidates(
    session: Session,
    candidates: list[OpenAccessPdfCandidate],
) -> list[OpenAccessPdfCandidate]:
    domains = {candidate.domain for candidate in candidates if candidate.domain is not None}
    health_by_domain = source_domain_health(session, domains)
    source_kind_bonus = {
        "arxiv_pdf": 0.09,
        "biorxiv_jats_xml": 0.09,
        "medrxiv_jats_xml": 0.09,
        "chemrxiv_pdf": 0.09,
        "openalex_content_pdf": 0.08,
        "openalex_content_grobid_xml": 0.08,
        "biorxiv_pdf": 0.08,
        "medrxiv_pdf": 0.08,
        "europe_pmc_oa_xml": 0.07,
        "core_download_url_pdf": 0.07,
        "core_source_fulltext_pdf": 0.06,
        "core_api_download_pdf": 0.05,
        "unpaywall_best_oa_pdf": 0.05,
        "unpaywall_oa_pdf": 0.03,
        "openalex_best_oa_location": 0.04,
        "openalex_primary_location": 0.02,
        "openalex_location": 0.01,
        "paper_pdf_url": 0.0,
    }

    def score(indexed: tuple[int, OpenAccessPdfCandidate]) -> tuple[float, int]:
        index, candidate = indexed
        health = health_by_domain.get(candidate.domain or "")
        quality = health.quality_score if health is not None else 0.5
        return (quality + source_kind_bonus.get(candidate.source_kind, 0.0), -index)

    return [
        candidate
        for _, candidate in sorted(
            enumerate(candidates),
            key=score,
            reverse=True,
        )
    ]


def _convert_resolver_result_to_candidate(
    result: Any, paper: Paper
) -> OpenAccessPdfCandidate | None:
    """Convert SciHubResult or LibGenResult to OpenAccessPdfCandidate."""
    if not HAS_RESOLVERS:
        return None
    
    # Handle SciHubResult
    if hasattr(result, "pdf_url") and hasattr(result, "source_kind"):
        pdf_url = result.pdf_url
        if pdf_url and isinstance(pdf_url, str) and pdf_url.startswith(("http://", "https://")):
            source_kind = getattr(result, "source_kind", "unknown_pdf")
            return OpenAccessPdfCandidate(
                url=pdf_url,
                license=paper.license,
                source_kind=str(source_kind),
                media_type="pdf",
                source_record_id=getattr(result, "identifier", None),
            )
    
    # Handle LibGenResult
    if hasattr(result, "pdf_url") and getattr(result, "source_kind", "").startswith("libgen"):
        pdf_url = result.pdf_url
        if pdf_url and isinstance(pdf_url, str) and pdf_url.startswith(("http://", "https://")):
            return OpenAccessPdfCandidate(
                url=pdf_url,
                license=paper.license,
                source_kind=getattr(result, "source_kind", "libgen_pdf"),
                media_type="pdf",
                source_record_id=getattr(result, "identifier", None),
            )
    
    return None


def full_text_source_stats(session: Session, *, limit: int = 20) -> dict[str, list[dict[str, object]]]:
    success = func.sum(case((FullTextSourceAttempt.status == "completed", 1), else_=0))
    total = func.count(FullTextSourceAttempt.id)

    domain_rows = session.execute(
        select(FullTextSourceAttempt.domain, total.label("attempts"), success.label("successes"))
        .where(FullTextSourceAttempt.domain.is_not(None))
        .group_by(FullTextSourceAttempt.domain)
        .order_by(total.desc())
        .limit(max(limit, 1))
    ).all()
    publisher_rows = session.execute(
        select(FullTextSourceAttempt.publisher, total.label("attempts"), success.label("successes"))
        .where(FullTextSourceAttempt.publisher.is_not(None))
        .group_by(FullTextSourceAttempt.publisher)
        .order_by(total.desc())
        .limit(max(limit, 1))
    ).all()
    failure_rows = session.execute(
        select(FullTextSourceAttempt.failure_kind, func.count(FullTextSourceAttempt.id))
        .where(FullTextSourceAttempt.failure_kind.is_not(None))
        .group_by(FullTextSourceAttempt.failure_kind)
        .order_by(func.count(FullTextSourceAttempt.id).desc())
    ).all()

    def normalize(rows: Sequence[Any], label: str) -> list[dict[str, object]]:
        result: list[dict[str, object]] = []
        for row in rows:
            name, attempts, successes = cast(tuple[Any, Any, Any], tuple(row))
            attempt_count = int(attempts or 0)
            success_count = int(successes or 0)
            result.append(
                {
                    label: name,
                    "attempts": attempt_count,
                    "successes": success_count,
                    "success_rate": round(success_count / attempt_count, 4) if attempt_count else 0.0,
                    "quality_score": round((success_count + 2) / (attempt_count + 4), 4),
                    "routing": (
                        "deprioritize"
                        if attempt_count >= 3 and success_count / attempt_count <= 0.25
                        else "normal"
                    ),
                }
            )
        return result

    return {
        "domains": normalize(domain_rows, "domain"),
        "publishers": normalize(publisher_rows, "publisher"),
        "failure_kinds": [
            {"failure_kind": failure_kind, "attempts": int(count)}
            for failure_kind, count in failure_rows
        ],
    }


# =============================================================================
# Sci-Hub Source Resolver (FullTextSourceResolver implementation)
# =============================================================================


class SciHubSourceResolver:
    """Sci-Hub resolver implementing FullTextSourceResolver protocol."""

    def __init__(
        self,
        settings: Settings,
        client: httpx.Client | None = None,
        sleeper: Callable[[float], None] = lambda x: __import__("time").sleep(x),
    ) -> None:
        from research_lab.resolvers.sci_hub import SciHubResolver as InternalSciHubResolver

        self._internal_resolver = InternalSciHubResolver(settings, client, sleeper)

    def resolve(
        self,
        paper: Paper,
        *,
        exclude_urls: set[str] | None = None,
    ) -> list[OpenAccessPdfCandidate]:
        """Resolve paper to Sci-Hub PDF candidates."""
        excluded = exclude_urls or set()
        candidates: list[OpenAccessPdfCandidate] = []

        # Try DOI first
        if paper.doi:
            result = self._internal_resolver.resolve(paper.doi, identifier_type="doi")
            candidate = convert_resolver_result_to_candidate(result)
            if candidate and candidate.url not in excluded:
                candidates.append(candidate)

        # Try PMID if available
        if not candidates and paper.pubmed_id:
            result = self._internal_resolver.resolve(str(paper.pubmed_id), identifier_type="pmid")
            candidate = convert_resolver_result_to_candidate(result)
            if candidate and candidate.url not in excluded:
                candidates.append(candidate)

        return candidates


# =============================================================================
# LibGen Source Resolver (FullTextSourceResolver implementation)
# =============================================================================


class LibGenSourceResolver:
    """LibGen resolver implementing FullTextSourceResolver protocol."""

    def __init__(
        self,
        settings: Settings,
        client: httpx.Client | None = None,
    ) -> None:
        from research_lab.resolvers.libgen import LibGenResolver as InternalLibGenResolver

        self._internal_resolver = InternalLibGenResolver(settings, client)

    def resolve(
        self,
        paper: Paper,
        *,
        exclude_urls: set[str] | None = None,
    ) -> list[OpenAccessPdfCandidate]:
        """Resolve paper to LibGen PDF candidates."""
        excluded = exclude_urls or set()
        candidates: list[OpenAccessPdfCandidate] = []

        # Try DOI first
        if paper.doi:
            result = self._internal_resolver.resolve_by_doi(paper.doi)
            candidate = convert_resolver_result_to_candidate(result)
            if candidate and candidate.url not in excluded:
                candidates.append(candidate)

        # Try ISBN if available
        if not candidates and paper.isbn:
            result = self._internal_resolver.resolve_by_isbn(str(paper.isbn))
            candidate = convert_resolver_result_to_candidate(result)
            if candidate and candidate.url not in excluded:
                candidates.append(candidate)

        return candidates


__all__ = (
    "FullTextSourceResolver",
    "OpenAlexSourceResolver",
    "EuropePmcSourceResolver",
    "ArxivResolver",
    "UnpaywallSourceResolver",
    "CoreSourceResolver",
    "PreprintSourceResolver",
    "SciHubSourceResolver",
    "LibGenSourceResolver",
    "OpenAccessPdfCandidate",
    "rank_open_access_candidates",
    "direct_repository_candidates",
    "should_refresh_before_direct_attempt",
)
