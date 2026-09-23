from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from research_lab.models import Base, Paper, PaperTopic, PaperTopicAssignmentEvidence, Topic
from research_lab.mot_classification import (
    classify_paper_mot,
    ensure_mot_topics,
    remove_current_automatic_mot_assignments,
)
from research_lab.mot_taxonomy import MOT_TAXONOMY_VERSION, infer_mot_assignments


def _slugs(title: str, abstract: str | None = None) -> set[str]:
    return {item.slug for item in infer_mot_assignments(title, abstract)}


def test_non_ai_technology_transfer_is_core_mot() -> None:
    slugs = _slugs(
        "University technology transfer and regional innovation",
        "We study licensing practices at technology transfer offices and university spin-offs.",
    )

    assert "mot-ip-licensing-transfer" in slugs
    assert "mot-relevance-core" in slugs
    assert "ai-role-unrelated" in slugs
    assert "ai-role-research-target" not in slugs


def test_ai_analysis_method_is_distinct_from_ai_research_target() -> None:
    method_only = _slugs(
        "Patent landscaping for technology foresight",
        "We use machine learning to analyze patent data and identify emerging technology trajectories.",
    )
    target_and_method = _slugs(
        "Artificial intelligence adoption in manufacturing firms",
        "We use machine learning classification to analyze determinants of artificial intelligence adoption.",
    )

    assert "ai-role-analysis-method" in method_only
    assert "ai-role-research-target" not in method_only
    assert "ai-role-analysis-method" in target_and_method
    assert "ai-role-research-target" in target_and_method


def test_dimensions_are_not_collapsed_into_one_tree() -> None:
    slugs = _slugs(
        "Open innovation networks in renewable energy manufacturing",
        "A firm-level panel data study of absorptive capacity and collaboration networks.",
    )

    assert "mot-open-innovation-networks-ecosystems" in slugs
    assert "context-energy-environment" in slugs
    assert "context-manufacturing" in slugs
    assert "unit-firm" in slugs
    assert "theory-absorptive-capacity" in slugs
    assert "mot-method-panel-causal" in slugs


def test_assignment_evidence_is_idempotent_and_versioned() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        paper = Paper(
            title="Technology transfer through patent licensing",
            abstract="University technology transfer offices manage patent licensing and commercialization.",
            publication_year=2010,
            primary_source="test",
            source_record_id="mot-test-1",
            retrieved_at=datetime.now(UTC),
            provenance={},
        )
        session.add(paper)
        session.flush()
        topics = ensure_mot_topics(session)

        first = classify_paper_mot(session, paper, topics_by_slug=topics)
        session.flush()
        second = classify_paper_mot(session, paper, topics_by_slug=topics)
        session.flush()

        assert first[0] > 0
        assert first[1] > 0
        assert second[0] == 0
        assert second[1] == 0
        topic = session.scalar(select(Topic).where(Topic.slug == "mot-ip-licensing-transfer"))
        assert topic is not None
        assert session.get(PaperTopic, {"paper_id": paper.id, "topic_id": topic.id}) is not None
        evidence_count = session.scalar(
            select(func.count()).select_from(PaperTopicAssignmentEvidence).where(
                PaperTopicAssignmentEvidence.paper_id == paper.id,
                PaperTopicAssignmentEvidence.topic_id == topic.id,
            )
        )
        assert evidence_count == 1


def test_human_rejected_current_assignment_is_not_recreated() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        paper = Paper(
            title="University technology transfer and patent licensing",
            abstract="Technology transfer offices manage licensing and commercialization.",
            publication_year=2012,
            primary_source="test",
            source_record_id="mot-test-rejected",
            retrieved_at=datetime.now(UTC),
            provenance={},
        )
        session.add(paper)
        session.flush()
        topics = ensure_mot_topics(session)
        topic = topics["mot-ip-licensing-transfer"]
        session.add(
            PaperTopicAssignmentEvidence(
                paper_id=paper.id,
                topic_id=topic.id,
                assignment_key="rejected-current-assignment".ljust(64, "0")[:64],
                taxonomy_version=MOT_TAXONOMY_VERSION,
                assignment_source="human_review",
                rule_id="human-review",
                evidence_kind="abstract",
                evidence_text="Reviewer rejected this automatic candidate.",
                source_locator="abstract",
                matched_terms=["technology transfer"],
                review_status="human_rejected",
            )
        )
        session.flush()

        links, evidence, _ = classify_paper_mot(session, paper, topics_by_slug=topics)
        session.flush()

        assert session.get(PaperTopic, {"paper_id": paper.id, "topic_id": topic.id}) is None
        assert links >= 0
        assert evidence >= 0
        rows = list(
            session.scalars(
                select(PaperTopicAssignmentEvidence).where(
                    PaperTopicAssignmentEvidence.paper_id == paper.id,
                    PaperTopicAssignmentEvidence.topic_id == topic.id,
                )
            )
        )
        assert len(rows) == 1
        assert rows[0].review_status == "human_rejected"


def test_reclassification_keeps_human_confirmed_link_and_historical_evidence() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        paper = Paper(
            title="Technology transfer through patent licensing",
            abstract="University technology transfer offices manage patent licensing.",
            publication_year=2010,
            primary_source="test",
            source_record_id="mot-test-confirmed",
            retrieved_at=datetime.now(UTC),
            provenance={},
        )
        session.add(paper)
        session.flush()
        topics = ensure_mot_topics(session)
        topic = topics["mot-ip-licensing-transfer"]
        classify_paper_mot(session, paper, topics_by_slug=topics)
        session.flush()
        session.add(
            PaperTopicAssignmentEvidence(
                paper_id=paper.id,
                topic_id=topic.id,
                assignment_key="confirmed-current-assignment".ljust(64, "0")[:64],
                taxonomy_version=MOT_TAXONOMY_VERSION,
                assignment_source="human_review",
                rule_id="human-review",
                evidence_kind="abstract",
                evidence_text="Reviewer confirmed the technology-transfer classification.",
                source_locator="abstract",
                matched_terms=["technology transfer"],
                review_status="human_confirmed",
            )
        )
        session.flush()

        removed = remove_current_automatic_mot_assignments(session, paper.id)
        session.flush()

        assert removed >= 0
        assert session.get(PaperTopic, {"paper_id": paper.id, "topic_id": topic.id}) is not None
        evidence_rows = list(
            session.scalars(
                select(PaperTopicAssignmentEvidence).where(
                    PaperTopicAssignmentEvidence.paper_id == paper.id,
                    PaperTopicAssignmentEvidence.topic_id == topic.id,
                )
            )
        )
        assert {row.review_status for row in evidence_rows} == {
            "automatic_candidate",
            "human_confirmed",
        }
