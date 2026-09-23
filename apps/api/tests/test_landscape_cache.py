from __future__ import annotations

from datetime import UTC, datetime

import research_lab.api as api
from research_lab.schemas import LandscapeResponse


def _response(total: int) -> LandscapeResponse:
    return LandscapeResponse(
        total_papers=total,
        abstract_papers=0,
        full_text_papers=0,
        full_text_queued=0,
        oa_papers=0,
        axes=[],
        subaxes=[],
        methodologies=[],
        years=[],
        top_authors=[],
        top_institutions=[],
        top_venues=[],
        last_ingestion_at=datetime.now(UTC),
    )


def test_landscape_route_reuses_cached_response(monkeypatch) -> None:
    calls = 0

    def fake_get_landscape(_db) -> LandscapeResponse:
        nonlocal calls
        calls += 1
        return _response(calls)

    monkeypatch.setattr(api, "get_landscape", fake_get_landscape)
    monkeypatch.setattr(api, "_landscape_cache", None)

    first = api.landscape(object())  # type: ignore[arg-type]
    second = api.landscape(object())  # type: ignore[arg-type]

    assert first.total_papers == 1
    assert second.total_papers == 1
    assert calls == 1
