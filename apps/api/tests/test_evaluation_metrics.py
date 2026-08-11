from research_lab.evaluation import ndcg_at_k, recall_at_k, reciprocal_rank


def test_recall_at_k_counts_relevant_hits() -> None:
    assert recall_at_k(["a", "b", "c"], {"a", "c", "z"}, 3) == 2 / 3
    assert recall_at_k(["x"] * 5 + ["a", "b"], {"a", "b"}, 10) == 1.0


def test_ndcg_is_one_for_ideal_binary_ranking() -> None:
    assert ndcg_at_k(["a", "b", "c"], {"a", "b"}, 3) == 1.0


def test_reciprocal_rank_uses_first_relevant_hit() -> None:
    assert reciprocal_rank(["x", "a", "b"], {"a", "b"}) == 0.5
