from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from research_lab.corpus_intelligence import list_research_opportunities
from research_lab.models import Base, Paper, ResearchOpportunity, ResearchSignalExtract
from research_lab.research_opportunity_signals import refresh_signal_research_opportunities


def _paper(title: str, year: int) -> Paper:
    return Paper(
        title=title,
        abstract="AI research opportunity signal fixture.",
        publication_year=year,
        primary_source="test",
        source_record_id=title,
        retrieved_at=datetime.now(UTC),
        provenance={},
    )


def _extract(
    paper: Paper,
    *,
    signal_type: str,
    label: str,
    card_id: uuid.UUID,
    evidence_text: str,
) -> ResearchSignalExtract:
    return ResearchSignalExtract(
        research_card_id=card_id,
        paper_id=paper.id,
        signal_type=signal_type,
        label=label,
        normalized_label=label.lower().replace(" ", "_"),
        field_name="limitations" if signal_type == "limitation" else "methodology",
        evidence_text=evidence_text,
        source_locator="abstract",
        support_status="supported",
    )


def test_refresh_signal_opportunities_creates_intersection_candidates() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        papers = [_paper(f"paper {index}", 2026) for index in range(4)]
        session.add_all(papers)
        session.flush()
        for index, paper in enumerate(papers):
            card_id = uuid.UUID(f"00000000-0000-0000-0000-00000000010{index}")
            session.add(
                _extract(
                    paper,
                    signal_type="limitation",
                    label="Causality and endogeneity",
                    card_id=card_id,
                    evidence_text="The study cannot establish causality.",
                )
            )
            session.add(
                _extract(
                    paper,
                    signal_type="method",
                    label="Difference-in-differences",
                    card_id=card_id,
                    evidence_text="A future design should use difference-in-differences.",
                )
            )
        session.add(
            ResearchOpportunity(
                slug="coverage-legacy",
                title="Legacy coverage opportunity",
                hypothesis="Legacy hypothesis",
                rationale="Legacy rationale",
                coverage_count=1,
                adjacent_count=99,
                signals={"source": "coverage"},
                generated_at=datetime.now(UTC),
            )
        )
        session.commit()

        result = refresh_signal_research_opportunities(session, limit=5, min_intersection=3)
        response = list_research_opportunities(session, limit=2)

    assert result.upserted == 1
    assert response.items[0].slug.startswith("signal-")
    assert response.items[0].signals["source"] == "research_signal_extracts"
    assert response.items[0].coverage_count == 4
    assert response.items[0].recommended_method == "Difference-in-differences"
    assert response.items[1].slug == "coverage-legacy"

