from datetime import UTC, datetime

from research_lab.chat import (
    DeterministicEvidenceProvider,
    EvidenceSnippet,
    GeneratedParagraph,
    structural_unsupported_claim_rate,
)
from research_lab.models import Paper


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
