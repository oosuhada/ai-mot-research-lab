from __future__ import annotations

import uuid

from research_lab.retrieval import _broad_websearch_query, reciprocal_rank_fusion


def test_broad_websearch_query_uses_or_for_discovery_recall() -> None:
    assert _broad_websearch_query("AI adoption firm performance") == (
        "AI OR adoption OR firm OR performance"
    )


def test_rrf_rewards_overlap_between_lexical_and_vector_results() -> None:
    shared_id = uuid.uuid4()
    lexical_only_id = uuid.uuid4()
    vector_only_id = uuid.uuid4()

    shared = {
        "id": shared_id,
        "title": "Shared evidence paper",
        "is_oa": True,
    }
    lexical = [
        shared,
        {"id": lexical_only_id, "title": "Lexical paper", "is_oa": False},
    ]
    vector = [
        shared,
        {"id": vector_only_id, "title": "Vector paper", "is_oa": False},
    ]

    fused = reciprocal_rank_fusion(lexical, vector, limit=3)

    assert fused[0].id == shared_id
    assert fused[0].lexical_rank == 1
    assert fused[0].semantic_rank == 1
    assert fused[0].fused_score > fused[1].fused_score
