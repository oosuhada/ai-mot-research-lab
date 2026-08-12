from __future__ import annotations

from unittest.mock import MagicMock

from research_lab.config import Settings
from research_lab.observability import benchmark_retrieval


def test_benchmark_rejects_no_queries_only_by_contract_not_fake_metrics() -> None:
    # The benchmark owns a fixed representative query set; this verifies an invalid provider
    # is surfaced rather than silently returning placeholder latency numbers.
    session = MagicMock()
    try:
        benchmark_retrieval(session, Settings(_env_file=None), provider_name="unknown")
    except ValueError as exc:
        assert "Unknown embedding provider" in str(exc)
    else:
        raise AssertionError("Unknown provider should fail")
