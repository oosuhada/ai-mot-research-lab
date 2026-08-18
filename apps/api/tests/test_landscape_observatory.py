from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from research_lab.library import browse_papers, get_landscape
from research_lab.models import Base, Paper, PaperChunk, PaperContentProfile, PaperTopic, Topic
from research_lab.retrieval import SearchFilters


def _paper(*, title: str, year: int, abstract: str | None, is_oa: bool) -> Paper:
    return Paper(
        title=title,
        abstract=abstract,
        publication_year=year,
        is_oa=is_oa,
        primary_source="test",
        source_record_id=title.lower().replace(" ", "-"),
        retrieved_at=datetime.now(UTC),
        provenance={},
    )


def test_landscape_exposes_evidence_depth_years_methods_and_subaxis_parent() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        axis = Topic(
            slug="ai-adoption-business-value",
            display_name="AI adoption and business value",
            kind="research_axis",
        )
        subaxis = Topic(
            slug="organizational-readiness",
            display_name="Organizational readiness",
            kind="research_subaxis",
            parent_topic_id=axis.id,
        )
        method = Topic(
            slug="methodology-survey",
            display_name="Survey",
            kind="methodology",
        )
        session.add_all([axis, subaxis, method])
        session.flush()
        subaxis.parent_topic_id = axis.id

        deep = _paper(title="Deep paper", year=2026, abstract="Evidence-rich abstract", is_oa=True)
        abstract_only = _paper(title="Abstract paper", year=2025, abstract="Abstract only", is_oa=True)
        metadata_only = _paper(title="Metadata paper", year=2024, abstract=None, is_oa=False)
        session.add_all([deep, abstract_only, metadata_only])
        session.flush()

        for paper in (deep, abstract_only, metadata_only):
            session.add(PaperTopic(paper_id=paper.id, topic_id=axis.id, assignment_source="test"))
        for paper in (deep, abstract_only):
            session.add(PaperTopic(paper_id=paper.id, topic_id=subaxis.id, assignment_source="test"))
            session.add(PaperTopic(paper_id=paper.id, topic_id=method.id, assignment_source="test"))

        session.add_all(
            [
                PaperContentProfile(
                    paper_id=deep.id,
                    abstract_status="available",
                    full_text_status="available",
                ),
                PaperContentProfile(
                    paper_id=abstract_only.id,
                    abstract_status="available",
                    full_text_status="not_requested",
                ),
                PaperContentProfile(
                    paper_id=metadata_only.id,
                    abstract_status="missing",
                    full_text_status="not_requested",
                ),
                PaperChunk(
                    paper_id=deep.id,
                    section="Results",
                    source_locator="p. 4 · Results",
                    text="Grounded result text.",
                    text_hash="deep-paper-results",
                ),
            ]
        )
        session.commit()

        landscape = get_landscape(session)
        axis_row = next(item for item in landscape.axes if item.slug == axis.slug)
        subaxis_row = next(item for item in landscape.subaxes if item.slug == subaxis.slug)

        assert axis_row.paper_count == 3
        assert axis_row.abstract_paper_count == 2
        assert axis_row.full_text_paper_count == 1
        assert axis_row.oa_paper_count == 2
        assert [(item.year, item.paper_count) for item in axis_row.years] == [(2024, 1), (2025, 1), (2026, 1)]
        assert axis_row.top_methodologies[0].slug == "methodology-survey"
        assert axis_row.top_methodologies[0].paper_count == 2

        assert subaxis_row.parent_slug == axis.slug
        assert subaxis_row.paper_count == 2
        assert subaxis_row.full_text_paper_count == 1

        filtered = browse_papers(
            session,
            limit=10,
            cursor=None,
            filters=SearchFilters(axis=subaxis.slug),
        )
        assert {item.title for item in filtered.items} == {"Deep paper", "Abstract paper"}
