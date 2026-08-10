from __future__ import annotations

import random
import time
from collections.abc import Callable, Mapping
from typing import Any

import httpx


class ResilientHttpClient:
    def __init__(
        self,
        client: httpx.Client,
        *,
        max_attempts: int = 5,
        base_delay_seconds: float = 0.5,
        jitter_ratio: float = 0.2,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.client = client
        self.max_attempts = max_attempts
        self.base_delay_seconds = base_delay_seconds
        self.jitter_ratio = jitter_ratio
        self.sleeper = sleeper

    def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, str | int | float | bool | None] | None = None,
    ) -> dict[str, Any]:
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = self.client.get(url, params=params)
            except (httpx.TimeoutException, httpx.TransportError):
                if attempt == self.max_attempts:
                    raise
                self.sleeper(self._delay(attempt, None))
                continue

            if response.status_code == 429 or response.status_code >= 500:
                if attempt == self.max_attempts:
                    response.raise_for_status()
                self.sleeper(self._delay(attempt, response.headers.get("Retry-After")))
                continue

            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise TypeError("Expected a JSON object from provider")
            return payload

        raise RuntimeError("HTTP retry loop exited unexpectedly")

    def _delay(self, attempt: int, retry_after: str | None) -> float:
        if retry_after is not None:
            try:
                return max(float(retry_after), 0.0)
            except ValueError:
                pass

        exponential = self.base_delay_seconds * (2 ** (attempt - 1))
        jitter = random.uniform(0.0, exponential * self.jitter_ratio)
        return exponential + jitter

