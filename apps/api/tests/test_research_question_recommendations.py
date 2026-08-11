from research_lab.research_questions import _recommendation_score


def test_recommendation_score_exposes_query_citation_and_novelty_components() -> None:
    score, components, reasons = _recommendation_score(
        query_rank=1,
        backward_seed_count=1,
        forward_seed_count=1,
        connected_seed_count=2,
        reading_status=None,
    )

    assert round(score, 2) == 1.61
    assert components == {
        "query_relevance": 1.0,
        "backward_snowball": 0.18,
        "forward_snowball": 0.18,
        "multi_seed_bridge": 0.15,
        "unread_novelty": 0.10,
    }
    assert "multi_seed_bridge" in reasons
    assert "unread_or_unqueued" in reasons


def test_recommendation_score_does_not_add_novelty_for_in_progress_reading() -> None:
    _, components, reasons = _recommendation_score(
        query_rank=3,
        backward_seed_count=0,
        forward_seed_count=0,
        connected_seed_count=0,
        reading_status="reading",
    )

    assert components["unread_novelty"] == 0.0
    assert "unread_or_unqueued" not in reasons


def test_recommendation_score_caps_repeated_citation_seed_bonus() -> None:
    score, components, _ = _recommendation_score(
        query_rank=None,
        backward_seed_count=10,
        forward_seed_count=10,
        connected_seed_count=10,
        reading_status="unread",
    )

    assert components["backward_snowball"] == 0.54
    assert components["forward_snowball"] == 0.54
    assert round(score, 2) == 1.33
