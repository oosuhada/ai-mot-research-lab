from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from research_lab.models import (
    Author,
    Base,
    EvidenceClaim,
    Paper,
    PaperAuthor,
    PaperContentProfile,
    PaperResearchCard,
    PaperTopic,
    ResearchSignalExtract,
    Topic,
)
from research_lab.research_signals import get_research_signal_lift


def _paper(title: str, year: int, abstract: str = "") -> Paper:
    return Paper(
        title=title,
        abstract=abstract,
        publication_year=year,
        primary_source="test",
        source_record_id=f"{title}-{year}",
        retrieved_at=datetime.now(UTC),
        provenance={},
    )


def test_research_signal_lift_separates_signals_from_reviewed_cards() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        frontier_topic = Topic(
            slug="agentic-workflow-automation",
            display_name="Agentic workflow automation",
            kind="research_subaxis",
        )
        method_topic = Topic(
            slug="methodology-experiment",
            display_name="Experiment",
            kind="methodology",
        )
        author = Author(display_name="Frontier Researcher")
        session.add_all([frontier_topic, method_topic, author])
        session.flush()

        papers = [
            _paper(
                f"Agentic workflow paper {index}",
                2026 if index < 12 else 2023,
                "This study discusses causal identification, longitudinal evidence, and trust.",
            )
            for index in range(16)
        ]
        session.add_all(papers)
        session.flush()
        for index, paper in enumerate(papers):
            session.add(PaperTopic(paper_id=paper.id, topic_id=frontier_topic.id, assignment_source="test"))
            session.add(PaperTopic(paper_id=paper.id, topic_id=method_topic.id, assignment_source="test"))
            session.add(
                PaperContentProfile(
                    paper_id=paper.id,
                    abstract_status="available",
                    full_text_status="available" if index < 8 else "queued",
                )
            )
            if index < 5:
                session.add(
                    PaperAuthor(
                        paper_id=paper.id,
                        author_id=author.id,
                        author_position=index,
                    )
                )

        session.add(
            PaperResearchCard(
                paper_id=papers[0].id,
                status="reviewed",
                fields={
                    "limitations": {
                        "value_text": "The evidence is limited by a single-country sample.",
                        "support_status": "supported",
                        "origin": "paper_evidence",
                        "source_locator": "page:7",
                    }
                },
            )
        )
        session.flush()
        card = session.scalar(select(PaperResearchCard).where(PaperResearchCard.paper_id == papers[0].id))
        assert card is not None
        session.add(
            ResearchSignalExtract(
                research_card_id=card.id,
                paper_id=papers[0].id,
                signal_type="limitation",
                label="Single-country or narrow context",
                normalized_label="single-country-or-narrow-context",
                field_name="limitations",
                evidence_text="The evidence is limited by a single-country sample.",
                source_locator="page:7",
            )
        )
        session.add(
            EvidenceClaim(
                claim_text="A supported test claim",
                claim_kind="system_inference",
                support_status="insufficient_evidence",
            )
        )
        session.commit()

        response = get_research_signal_lift(session, limit=3)

    assert response.total_records == 16
    assert response.full_text_ready == 8
    assert response.research_cards_ready == 1
    assert response.reviewed_research_cards == 1
    assert response.evidence_claims == 1
    assert response.normalized_signals
    assert response.normalized_signals[0].label == "Single-country or narrow context"
    assert response.normalized_signals[0].example_paper_title == papers[0].title
    assert response.repeated_limitations
    assert response.repeated_limitations[0].signal_type == "repeated_limitation"
    assert response.card_evidence_signals
    assert response.card_evidence_signals[0].field_name == "limitations"
    assert response.card_evidence_signals[0].source_locator == "page:7"
    assert response.method_data_signals
    assert any(item.label == "Experiment" for item in response.method_data_signals)
    assert response.frontier_researchers[0].label == "Frontier Researcher"
    assert response.caveats
