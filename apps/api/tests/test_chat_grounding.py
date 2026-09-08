from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from research_lab.chat import (
    DeterministicEvidenceProvider,
    EvidenceSnippet,
    GeneratedParagraph,
    _scope_papers,
    structural_unsupported_claim_rate,
)
from research_lab.models import Paper
from research_lab.schemas import ChatRequest


def _paper() -> Paper:
    return Paper(
        title="AI capability and firm performance",
        abstract="Results show that AI capability is positively associated with firm performance.",
        publication_year=2024,
        is_oa=True,
        primary_source="test",
        source_record_id="chat-test",
        retrieved_at=datetime.now(UTC),
        provenance={},
    )


def test_deterministic_provider_cites_every_supported_paragraph() -> None:
    evidence = [
        EvidenceSnippet(
            paper=_paper(),
            excerpt="Results show that AI capability is positively associated with firm performance.",
            overlap_terms=("capability", "performance"),
        )
    ]
    paragraphs = DeterministicEvidenceProvider().generate("AI capability performance", evidence)

    assert paragraphs[0].support_status == "supported"
    assert paragraphs[0].citation_indexes == (1,)
    assert structural_unsupported_claim_rate(paragraphs) == 0.0


def test_insufficient_evidence_is_not_counted_as_unsupported_assertion() -> None:
    paragraphs = [
        GeneratedParagraph(
            text="Insufficient evidence.",
            claim_kind="system_inference",
            support_status="insufficient_evidence",
            citation_indexes=(),
        )
    ]

    assert structural_unsupported_claim_rate(paragraphs) == 0.0


def test_corpus_graphrag_uses_metadata_seeds_before_full_text_evidence() -> None:
    session = MagicMock()
    session.scalars.return_value.all.return_value = []
    graph_result = MagicMock(rows=[], trace=MagicMock())
    graph_service = MagicMock()
    graph_service.search.return_value = graph_result
    selection = MagicMock(provider=MagicMock())

    with (
        patch("research_lab.chat.HybridRetrievalService") as baseline_service,
        patch("research_lab.chat.GraphAugmentedRetrievalService", return_value=graph_service),
        patch("research_lab.chat.build_research_graph_service", return_value=MagicMock()),
        patch("research_lab.chat.choose_search_embedding_provider", return_value=selection),
    ):
        _scope_papers(
            session,
            ChatRequest(question="AI adoption firm performance", graph_mode="on"),
        )

    baseline_service.assert_called_once_with(session, selection.provider)
    assert graph_service.search.call_args.kwargs["scope"] == "metadata"


def test_corpus_baseline_chat_preserves_full_search_scope_when_graph_is_off() -> None:
    session = MagicMock()
    session.scalars.return_value.all.return_value = []
    graph_result = MagicMock(rows=[], trace=MagicMock())
    graph_service = MagicMock()
    graph_service.search.return_value = graph_result

    with (
        patch("research_lab.chat.HybridRetrievalService") as baseline_service,
        patch("research_lab.chat.GraphAugmentedRetrievalService", return_value=graph_service),
        patch("research_lab.chat.build_research_graph_service", return_value=None),
        patch("research_lab.chat.choose_search_embedding_provider") as choose_provider,
    ):
        _scope_papers(
            session,
            ChatRequest(question="AI adoption firm performance", graph_mode="off"),
        )

    baseline_service.assert_called_once_with(session)
    choose_provider.assert_not_called()
    assert graph_service.search.call_args.kwargs["scope"] == "all"
