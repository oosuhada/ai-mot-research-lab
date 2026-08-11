from research_lab.grounding_review import score_grounding_rows


def test_grounding_review_does_not_score_unreviewed_rows() -> None:
    result = score_grounding_rows(
        [
            {"human_label": ""},
            {"human_label": ""},
        ]
    )

    assert result["reviewed_pairs"] == 0
    assert result["human_reviewed_semantic_support_precision"] is None
    assert result["status"] == "awaiting_human_review"


def test_grounding_review_scores_only_explicit_human_labels() -> None:
    result = score_grounding_rows(
        [
            {"human_label": "supported"},
            {"human_label": "contradicted"},
            {"human_label": ""},
        ]
    )

    assert result["review_pairs"] == 3
    assert result["reviewed_pairs"] == 2
    assert result["review_coverage"] == 2 / 3
    assert result["human_reviewed_semantic_support_precision"] == 0.5
    assert result["contradicted_pairs"] == 1
