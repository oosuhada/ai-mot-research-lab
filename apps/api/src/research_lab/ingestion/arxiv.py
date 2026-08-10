from __future__ import annotations

import time
from collections.abc import Callable

import httpx

from research_lab.config import Settings


class ArxivClient:
    """Legacy arXiv API adapter with the documented >=3 second request spacing."""

    def __init__(
        self,
        settings: Settings,
        client: httpx.Client | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._owns_client = client is None
        self.client = client or httpx.Client(
            timeout=settings.request_timeout_seconds,
            headers={"User-Agent": "ai-mot-research-lab/0.1"},
        )
        self.base_url = settings.arxiv_base_url
        self.sleeper = sleeper
        self._last_request_at = 0.0

    def query(self, search_query: str, *, start: int = 0, max_results: int = 25) -> str:
        elapsed = time.monotonic() - self._last_request_at
        if self._last_request_at and elapsed < 3.0:
            self.sleeper(3.0 - elapsed)
        response = self.client.get(
            self.base_url,
            params={"search_query": search_query, "start": start, "max_results": max_results},
        )
        self._last_request_at = time.monotonic()
        response.raise_for_status()
        return response.text

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

