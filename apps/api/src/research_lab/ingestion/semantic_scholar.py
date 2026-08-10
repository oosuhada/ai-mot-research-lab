from __future__ import annotations

from typing import Any

import httpx

from research_lab.config import Settings
from research_lab.ingestion.http import ResilientHttpClient


class SemanticScholarClient:
    """Terms-gated optional enrichment; disabled unless an API key is configured."""

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        if not settings.semantic_scholar_api_key:
            raise RuntimeError(
                "Semantic Scholar enrichment is disabled. Configure a key only after reviewing current API terms."
            )
        headers = {
            "x-api-key": settings.semantic_scholar_api_key,
            "User-Agent": "ai-mot-research-lab/0.1",
        }
        self._owns_client = client is None
        self.client = client or httpx.Client(timeout=settings.request_timeout_seconds, headers=headers)
        self.http = ResilientHttpClient(self.client, base_delay_seconds=1.0)
        self.base_url = settings.semantic_scholar_base_url.rstrip("/")

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def paper_by_doi(self, doi: str) -> dict[str, Any]:
        return self.http.get_json(
            f"{self.base_url}/paper/DOI:{doi}",
            params={
                "fields": "paperId,title,citationCount,influentialCitationCount,externalIds,openAccessPdf"
            },
        )

