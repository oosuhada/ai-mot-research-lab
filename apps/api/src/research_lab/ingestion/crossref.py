from __future__ import annotations

from typing import Any

import httpx

from research_lab.config import Settings
from research_lab.ingestion.http import ResilientHttpClient


class CrossrefClient:
    """Conservative DOI metadata enrichment adapter; never blocks primary ingestion."""

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        headers = {
            "User-Agent": "ai-mot-research-lab/0.1 (personal research metadata client)",
            "Accept": "application/json",
        }
        self._owns_client = client is None
        self.client = client or httpx.Client(timeout=settings.request_timeout_seconds, headers=headers)
        self.http = ResilientHttpClient(self.client, base_delay_seconds=1.0)
        self.base_url = settings.crossref_base_url.rstrip("/")
        self.mailto = settings.crossref_mailto

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def lookup_doi(self, doi: str) -> dict[str, Any]:
        params = {"mailto": self.mailto} if self.mailto else None
        payload = self.http.get_json(f"{self.base_url}/works/{doi}", params=params)
        message = payload.get("message", {})
        return message if isinstance(message, dict) else {}

