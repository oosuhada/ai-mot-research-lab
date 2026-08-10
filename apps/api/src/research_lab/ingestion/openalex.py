from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx

from research_lab.config import Settings
from research_lab.ingestion.http import ResilientHttpClient
from research_lab.ingestion.normalization import normalize_doi, normalize_openalex_id
from research_lab.taxonomy import ResearchAxis


def reconstruct_abstract(inverted_index: dict[str, list[int]] | None) -> str | None:
    if not inverted_index:
        return None
    positions: list[tuple[int, str]] = []
    for token, token_positions in inverted_index.items():
        positions.extend((position, token) for position in token_positions)
    positions.sort(key=lambda item: item[0])
    return " ".join(token for _, token in positions)


@dataclass(frozen=True, slots=True)
class OpenAlexRecord:
    source_record_id: str
    doi: str | None
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

    def _normalize(self, work: dict[str, Any]) -> OpenAlexRecord:
        primary_location = work.get("primary_location") or {}
        source = primary_location.get("source") or {}
        open_access = work.get("open_access") or {}
        raw_date = work.get("publication_date")

        return OpenAlexRecord(
            source_record_id=normalize_openalex_id(work.get("id")) or str(work.get("id", "")),
            doi=normalize_doi(work.get("doi")),
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

