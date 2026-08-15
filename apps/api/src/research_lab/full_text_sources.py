from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, cast
from urllib.parse import urlparse

import httpx
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from research_lab.config import Settings
from research_lab.models import FullTextSourceAttempt, Paper


@dataclass(frozen=True, slots=True)
class OpenAccessPdfCandidate:
    url: str
    license: str | None
    source_kind: str
    request_params: tuple[tuple[str, str], ...] = field(default=(), repr=False, compare=False)

    @property
    def domain(self) -> str | None:
        hostname = urlparse(self.url).hostname
        return hostname.lower() if hostname else None


@dataclass(frozen=True, slots=True)
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


class OpenAccessSourceResolver:
    """Refresh rights-safe OpenAlex locations without bypassing publisher access controls."""

    def __init__(self, settings: Settings, client: httpx.Client) -> None:
        self.settings = settings
        self.client = client

    def resolve(self, paper: Paper, *, exclude_urls: set[str] | None = None) -> list[OpenAccessPdfCandidate]:
        excluded = exclude_urls or set()
        openalex_id = paper.openalex_id
        if not openalex_id and paper.primary_source == "openalex" and paper.source_record_id.startswith("W"):
            openalex_id = paper.source_record_id
        if not paper.is_oa or not openalex_id:
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

        candidates: list[OpenAccessPdfCandidate] = []
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
                    request_params=request_params,
                )
            )
        return candidates


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
        "openalex_content_pdf": 0.08,
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
