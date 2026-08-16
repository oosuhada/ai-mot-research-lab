from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx

from research_lab.config import Settings
from research_lab.ingestion.http import ResilientHttpClient
from research_lab.ingestion.normalization import normalize_arxiv_id, normalize_doi, normalize_openalex_id
from research_lab.taxonomy import ResearchAxis


def reconstruct_abstract(inverted_index: dict[str, list[int]] | None) -> str | None:
    if not inverted_index:
        return None
    positions: list[tuple[int, str]] = []
    for token, token_positions in inverted_index.items():
        positions.extend((position, token) for position in token_positions)
    positions.sort(key=lambda item: item[0])
    return " ".join(token for _, token in positions)


def extract_arxiv_id(work: dict[str, Any]) -> str | None:
    """Recover an arXiv identifier from OpenAlex location URLs when available."""
    ids = work.get("ids") or {}
    if isinstance(ids, dict):
        normalized = normalize_arxiv_id(ids.get("arxiv"))
        if normalized:
            return normalized

    raw_locations: list[dict[str, Any]] = []
    primary_location = work.get("primary_location")
    if isinstance(primary_location, dict):
        raw_locations.append(primary_location)
    locations = work.get("locations")
    if isinstance(locations, list):
        raw_locations.extend(location for location in locations if isinstance(location, dict))

    for location in raw_locations:
        for key in ("landing_page_url", "pdf_url"):
            raw_url = location.get(key)
            if not isinstance(raw_url, str):
                continue
            lowered = raw_url.lower()
            if "arxiv.org/abs/" in lowered or "arxiv.org/pdf/" in lowered or lowered.startswith("arxiv:"):
                normalized = normalize_arxiv_id(raw_url)
                if normalized:
                    return normalized
    return None


@dataclass(frozen=True, slots=True)
class OpenAlexRecord:
    source_record_id: str
    doi: str | None
    arxiv_id: str | None
    title: str
    abstract: str | None
    publication_date: date | None
    publication_year: int | None
    language: str | None
    work_type: str | None
    primary_url: str | None
    pdf_url: str | None
    is_oa: bool
    oa_status: str | None
    license: str | None
    publisher: str | None
    venue: dict[str, Any] | None
    authorships: list[dict[str, Any]]
    topics: list[dict[str, Any]]
    referenced_works: list[str]
    cited_by_count: int
    is_retracted: bool
    raw: dict[str, Any]


class OpenAlexClient:
    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        headers = {
            "User-Agent": "ai-mot-research-lab/0.1 (greenfield personal research tool)",
            "Accept": "application/json",
        }
        self._owns_client = client is None
        self.client = client or httpx.Client(timeout=settings.request_timeout_seconds, headers=headers)
        self.http = ResilientHttpClient(self.client)
        self.base_url = settings.openalex_base_url.rstrip("/")
        self.api_key = settings.openalex_api_key

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def iter_axis_records(
        self,
        axis: ResearchAxis,
        *,
        max_records: int,
        from_year: int = 2018,
        per_page: int = 100,
    ) -> Iterator[OpenAlexRecord]:
        fetched = 0
        page = 1

        while fetched < max_records:
            page_size = min(per_page, max_records - fetched)
            params: dict[str, str | int] = {
                "search": axis.openalex_query,
                "filter": f"from_publication_date:{from_year}-01-01",
                "per_page": page_size,
                "page": page,
            }
            if self.api_key:
                params["api_key"] = self.api_key

            payload = self.http.get_json(f"{self.base_url}/works", params=params)
            results = payload.get("results", [])
            if not isinstance(results, list) or not results:
                return

            for work in results:
                if isinstance(work, dict):
                    yield self._normalize(work)
                    fetched += 1
                    if fetched >= max_records:
                        return

            if len(results) < page_size:
                return
            page += 1

    def fetch_axis_year_page(
        self,
        axis: ResearchAxis,
        *,
        year: int,
        page: int,
        per_page: int = 100,
    ) -> tuple[list[OpenAlexRecord], int]:
        """Fetch one deterministic year-sliced page for resumable corpus expansion.

        Year slicing keeps each search below OpenAlex's 10,000-result basic-paging
        ceiling while allowing the long-running worker to checkpoint a simple page
        number after every request.
        """
        if page < 1 or page > 100:
            raise ValueError("OpenAlex basic paging supports pages 1 through 100")
        params: dict[str, str | int] = {
            "search": axis.openalex_query,
            "filter": (
                f"from_publication_date:{year}-01-01,"
                f"to_publication_date:{year}-12-31"
            ),
            "per_page": min(max(per_page, 1), 100),
            "page": page,
        }
        if self.api_key:
            params["api_key"] = self.api_key
        payload = self.http.get_json(f"{self.base_url}/works", params=params)
        raw_results = payload.get("results", [])
        results = [
            self._normalize(work)
            for work in raw_results
            if isinstance(work, dict)
        ] if isinstance(raw_results, list) else []
        meta = payload.get("meta") or {}
        total = int(meta.get("count") or 0) if isinstance(meta, dict) else 0
        return results, total

    def fetch_axis_date_page(
        self,
        axis: ResearchAxis,
        *,
        from_date: date,
        to_date: date,
        page: int,
        per_page: int = 100,
    ) -> tuple[list[OpenAlexRecord], int]:
        """Fetch a recent publication-date window without sharing expansion state."""
        if from_date > to_date:
            raise ValueError("from_date must be on or before to_date")
        if page < 1 or page > 100:
            raise ValueError("OpenAlex basic paging supports pages 1 through 100")
        params: dict[str, str | int] = {
            "search": axis.openalex_query,
            "filter": (
                f"from_publication_date:{from_date.isoformat()},"
                f"to_publication_date:{to_date.isoformat()}"
            ),
            "sort": "publication_date:desc",
            "per_page": min(max(per_page, 1), 100),
            "page": page,
        }
        if self.api_key:
            params["api_key"] = self.api_key
        payload = self.http.get_json(f"{self.base_url}/works", params=params)
        raw_results = payload.get("results", [])
        results = (
            [self._normalize(work) for work in raw_results if isinstance(work, dict)]
            if isinstance(raw_results, list)
            else []
        )
        meta = payload.get("meta") or {}
        total = int(meta.get("count") or 0) if isinstance(meta, dict) else 0
        return results, total

    def lookup_doi(self, doi: str) -> OpenAlexRecord | None:
        params: dict[str, str | int] = {"filter": f"doi:{doi}", "per_page": 1}
        if self.api_key:
            params["api_key"] = self.api_key
        payload = self.http.get_json(f"{self.base_url}/works", params=params)
        results = payload.get("results", [])
        if not isinstance(results, list) or not results or not isinstance(results[0], dict):
            return None
        return self._normalize(results[0])

    def _normalize(self, work: dict[str, Any]) -> OpenAlexRecord:
        primary_location = work.get("primary_location") or {}
        source = primary_location.get("source") or {}
        open_access = work.get("open_access") or {}
        raw_date = work.get("publication_date")

        return OpenAlexRecord(
            source_record_id=normalize_openalex_id(work.get("id")) or str(work.get("id", "")),
            doi=normalize_doi(work.get("doi")),
            arxiv_id=extract_arxiv_id(work),
            title=str(work.get("title") or "Untitled work"),
            abstract=reconstruct_abstract(work.get("abstract_inverted_index")),
            publication_date=date.fromisoformat(raw_date) if raw_date else None,
            publication_year=work.get("publication_year"),
            language=work.get("language"),
            work_type=work.get("type"),
            primary_url=primary_location.get("landing_page_url") or work.get("id"),
            pdf_url=primary_location.get("pdf_url") if primary_location.get("is_oa") else None,
            is_oa=bool(open_access.get("is_oa")),
            oa_status=open_access.get("oa_status"),
            license=primary_location.get("license"),
            publisher=source.get("host_organization_name"),
            venue=source if source else None,
            authorships=list(work.get("authorships") or []),
            topics=list(work.get("topics") or []),
            referenced_works=list(work.get("referenced_works") or []),
            cited_by_count=int(work.get("cited_by_count") or 0),
            is_retracted=bool(work.get("is_retracted")),
            raw=work,
        )
