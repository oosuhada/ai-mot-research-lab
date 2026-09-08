from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import MagicMock

from sqlalchemy.orm import Session

from research_lab.research_graph import (
    GraphAugmentedRetrievalService,
    ResearchGraphService,
    graph_signal_score,
)
from research_lab.retrieval import HybridRetrievalService, RankedPaper


class FakeGraphProvider:
    name = "fake_graph"

    def __init__(self, candidate_id: uuid.UUID) -> None:
        self.candidate_id = candidate_id
        self.statements: list[str] = []

    def run(self, statement: str, parameters: object = None) -> list[dict[str, object]]:
        self.statements.append(statement)
        if "RETURN 1 AS ok" in statement:
            return [{"ok": 1}]
        if ":CITES*" in statement:
            return [
                {
                    "paper_id": str(self.candidate_id),
                    "distance": 1,
                    "citation_paths": 3,
                    "page_rank": 1.5,
                }
            ]
        if "HAS_TOPIC" in statement:
            return [{"paper_id": str(self.candidate_id), "shared_topics": 2, "page_rank": 1.5}]
        if "AFFILIATED_WITH" in statement:
            return [{"paper_id": str(self.candidate_id), "shared_institutions": 1, "page_rank": 1.5}]
        if "AUTHORED" in statement:
            return [{"paper_id": str(self.candidate_id), "shared_authors": 1, "page_rank": 1.5}]
        if "citationCommunity IN communities" in statement:
            return [{"paper_id": str(self.candidate_id), "same_community": True, "page_rank": 1.5}]
        return []


class FailingGraphProvider:
    name = "failing_graph"

    def run(self, statement: str, parameters: object = None) -> list[dict[str, object]]:
        raise RuntimeError("graph offline")


def _ranked(paper_id: uuid.UUID) -> RankedPaper:
    return RankedPaper(
        id=paper_id,
        doi=None,
        openalex_id=None,
        title="Seed paper",
        abstract="Evidence",
        publication_date=date(2025, 1, 1),
        publication_year=2025,
        work_type="article",
        venue_name=None,
        oa_status=None,
        is_oa=False,
        primary_url=None,
        pdf_url=None,
        license=None,
        lexical_rank=1,
        semantic_rank=1,
        fused_score=0.03,
        rerank_score=None,
        matched_source="abstract",
        matched_locator="abstract",
        matched_excerpt="Evidence",
        citation_count=0,
        reading_priority=0,
    )


def test_graph_expansion_merges_bounded_relation_signals() -> None:
    seed_id = uuid.uuid4()
    candidate_id = uuid.uuid4()
    provider = FakeGraphProvider(candidate_id)
    service = ResearchGraphService(provider, result_cap=20)

    rows = service.expand_paper_seeds([seed_id], hops=9, limit=20)

    assert len(rows) == 1
    row = rows[0]
    assert row.paper_id == candidate_id
    assert row.distance == 1
    assert row.citation_paths == 3
    assert row.shared_topics == 2
    assert row.shared_authors == 1
    assert row.shared_institutions == 1
    assert row.same_community is True
    assert row.reasons == {"citation", "topic", "author", "institution", "community"}
    assert any(":CITES*1..2" in statement for statement in provider.statements)
    assert graph_signal_score(row) > 0.5


def test_graph_retrieval_gracefully_falls_back_when_provider_is_offline() -> None:
    seed = _ranked(uuid.uuid4())
    baseline = MagicMock(spec=HybridRetrievalService)
    baseline.search.return_value = [seed]
    graph = ResearchGraphService(FailingGraphProvider())
    service = GraphAugmentedRetrievalService(MagicMock(spec=Session), baseline, graph)

    result = service.search("AI adoption", graph_mode="on", limit=10)

    assert result.rows == [seed]
    assert result.trace.applied is False
    assert result.trace.provider == "failing_graph"
    assert result.trace.expansion_count == 0
    assert result.trace.fallback_reason == "graph offline"


def test_graph_off_mode_never_calls_provider() -> None:
    seed = _ranked(uuid.uuid4())
    baseline = MagicMock(spec=HybridRetrievalService)
    baseline.search.return_value = [seed]
    provider = MagicMock()
    provider.name = "should_not_run"
    graph = ResearchGraphService(provider)
    service = GraphAugmentedRetrievalService(MagicMock(spec=Session), baseline, graph)

    result = service.search("AI adoption", graph_mode="off", limit=10)

    assert result.rows == [seed]
    assert result.trace.applied is False
    provider.run.assert_not_called()
