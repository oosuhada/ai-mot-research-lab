from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from research_lab.retrieval import (
    HybridRetrievalService,
    SearchFilters,
    _broad_websearch_query,
    reciprocal_rank_fusion,
)


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


def test_filter_sql_keeps_personal_and_scholarly_filters_on_same_paper_scope() -> None:
    service = HybridRetrievalService(MagicMock(spec=Session))
    sql, params = service._filter_sql(
        SearchFilters(
            year_from=2020,
            year_to=2025,
            axis="ai-governance-responsible-deployment",
            methodology="survey",
            is_oa=True,
            reading_status="reading",
            tag="dissertation",
        )
    )
    assert "p.publication_year >= :year_from" in sql
    assert "t.kind = 'research_axis'" in sql
    assert "t.kind = 'methodology'" in sql
    assert "reading_queue" in sql
    assert "paper_tags" in sql
    assert params["methodology"] == "methodology-survey"
    assert params["reading_status"] == "reading"


def test_candidate_pool_depth_is_stable_across_requested_result_limits() -> None:
    service = HybridRetrievalService(MagicMock(spec=Session))
    lexical = MagicMock(return_value=[])
    vector = MagicMock(return_value=[])

    with (
        patch.object(service, "_lexical_search", lexical),
        patch.object(service, "_vector_search", vector),
    ):
        service.search("AI adoption", mode="hybrid", limit=10)
        service.search("AI adoption", mode="hybrid", limit=30)

    assert [call.args[1] for call in lexical.call_args_list] == [100, 100]
    assert [call.args[1] for call in vector.call_args_list] == [100, 100]


def test_vector_search_enables_filtered_hnsw_iterative_scan() -> None:
    session = MagicMock(spec=Session)
    service = HybridRetrievalService(session)
    service._enable_filtered_hnsw_scan()

    statement = session.execute.call_args.args[0]
    assert "hnsw.iterative_scan" in str(statement)
    assert "strict_order" in str(statement)
