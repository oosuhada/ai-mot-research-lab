from research_lab.corpus_bulk_bootstrap import (
    BulkBootstrapState,
    OpenAlexBulkBootstrapWorker,
    _next_bulk_slice_index,
)
from research_lab.corpus_expansion import ExpansionState, _hydrate_round_robin_state, _next_slice_index


def test_round_robin_preserves_legacy_checkpoint_and_advances_slice() -> None:
    slices = [("adoption", 2026), ("innovation", 2026), ("adoption", 2025)]
    state = ExpansionState(target_total=100_000, from_year=2017, to_year=2026, page=58)

    _hydrate_round_robin_state(state, slices)

    assert state.slice_pages["adoption:2026"] == 58
    assert _next_slice_index(slices, 0, set()) == 1


def test_round_robin_skips_completed_slices() -> None:
    slices = [("adoption", 2026), ("innovation", 2026), ("adoption", 2025)]
    assert _next_slice_index(slices, 0, {"innovation:2026"}) == 2


def test_bulk_round_robin_can_resume_current_slice_then_advance() -> None:
    slices = [("adoption", 2026), ("innovation", 2026), ("adoption", 2025)]

    assert _next_bulk_slice_index(slices, 1, set()) == 1
    assert _next_bulk_slice_index(slices, 1, set(), advance=True) == 2
    assert _next_bulk_slice_index(slices, 1, {"adoption:2025"}, advance=True) == 0


def test_bulk_daily_request_counter_resets_on_new_utc_day() -> None:
    state = BulkBootstrapState(
        target_total=100_000,
        from_year=2017,
        to_year=2026,
        request_day="2000-01-01",
        requests_today=480,
    )

    OpenAlexBulkBootstrapWorker._refresh_daily_counter(state)

    assert state.request_day != "2000-01-01"
    assert state.requests_today == 0
