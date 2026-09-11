from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from research_lab.models import Base, Paper, PaperResearchCard, ResearchSignalExtract
from research_lab.research_signal_extracts import (
    backfill_research_signal_extracts,
    extract_signals_from_card,
)
from research_lab.schemas import ResearchCardField


def _paper() -> Paper:
    return Paper(
        title="AI capability and innovation performance",
        abstract="AI capability research.",
        publication_year=2026,
        primary_source="test",
        source_record_id="signal-extract-paper",
        retrieved_at=datetime.now(UTC),
        provenance={},
    )


def _field(value: str, locator: str = "abstract") -> dict[str, object]:
    return ResearchCardField(
        value_text=value,
        origin="paper_evidence",
        support_status="supported",
        source_locator=locator,
    ).model_dump(mode="json")


def test_extract_signals_from_card_normalizes_evidence_fields() -> None:
    paper = _paper()
    card = PaperResearchCard(
        paper_id=paper.id,
        fields={
            "limitations": _field("The study uses a cross-sectional survey and has common method bias."),
            "dataset_and_sample": _field("Panel data from manufacturing firms and financial performance data."),
            "methodology": _field("The analysis uses structural equation modeling and regression."),
            "findings": _field("AI capability is associated with innovation performance."),
            "future_research": _field("Future research should use longitudinal data for causal identification."),
        },
    )

    extracts = extract_signals_from_card(card, paper)
    labels = {(row.signal_type, row.label) for row in extracts}

    assert ("limitation", "Cross-sectional design") in labels
    assert ("limitation", "Self-report and common method bias") in labels
    assert ("dataset", "Panel or longitudinal data") in labels
    assert ("dataset", "Financial or firm-performance data") in labels
    assert ("method", "Structural equation modeling") in labels
    assert ("method", "Regression or econometric model") in labels
    assert ("evaluation_metric", "Innovation performance") in labels
    assert ("future_research", "Causal identification") in labels


def test_extract_signals_respects_word_boundaries_for_short_terms() -> None:
    paper = _paper()
    card = PaperResearchCard(
        paper_id=paper.id,
        fields={
            "methodology": _field("The system is evaluated with workflow logs."),
        },
    )

    extracts = extract_signals_from_card(card, paper)

    assert all(row.label != "Structural equation modeling" for row in extracts)


def test_backfill_research_signal_extracts_is_idempotent() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        paper = _paper()
        session.add(paper)
        session.flush()
        session.add(
            PaperResearchCard(
                paper_id=paper.id,
                fields={
                    "limitations": _field("The evidence is cross-sectional and has limited generalizability."),
                    "methodology": _field("The study uses a survey and structural equation modeling."),
                },
            )
        )
        session.commit()

        first = backfill_research_signal_extracts(session, limit=10)
        second = backfill_research_signal_extracts(session, limit=10)
        extracts = session.scalars(select(ResearchSignalExtract)).all()

    assert first.selected == 1
    assert first.cards_processed == 1
    assert first.extracts_created >= 3
    assert second.selected == 0
    assert second.extracts_created == 0
    assert len(extracts) == first.extracts_created
