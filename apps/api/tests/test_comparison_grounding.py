from datetime import UTC, datetime

from research_lab.comparison import extract_comparison_fields
from research_lab.models import Paper


def test_comparison_extracts_only_abstract_backed_fields() -> None:
    paper = Paper(
        title="AI capability and firm performance",
        abstract=(
            "This study examines AI capability using the resource-based view. "
            "A survey of 210 firms uses structural equation modelling. "
            "Results show a positive association with organizational performance."
        ),
        publication_year=2024,
        is_oa=True,
        primary_source="test",
        source_record_id="test-1",
        retrieved_at=datetime.now(UTC),
        provenance={},
    )

    fields = extract_comparison_fields(paper)

    assert fields["research_question"].support_status == "supported"
    assert fields["theoretical_lens"].value_text == "resource-based view"
    assert fields["methodology"].support_status == "supported"
    assert fields["dataset_and_sample"].value_text == "210 firms"
    assert fields["findings"].support_status == "supported"
    assert fields["limitations"].support_status == "insufficient_evidence"
    assert fields["limitations"].source_locator is None


def test_comparison_without_abstract_never_fabricates_fields() -> None:
    paper = Paper(
        title="Metadata-only paper",
        abstract=None,
        is_oa=False,
        primary_source="test",
        source_record_id="test-2",
        retrieved_at=datetime.now(UTC),
        provenance={},
    )

    fields = extract_comparison_fields(paper)

    assert all(field.support_status == "insufficient_evidence" for field in fields.values())
    assert all(field.source_locator is None for field in fields.values())
