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
