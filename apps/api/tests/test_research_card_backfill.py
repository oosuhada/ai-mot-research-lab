from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from research_lab.models import (
    CitationSnapshot,
    EvidenceClaim,
    EvidenceLink,
    Paper,
    PaperChunk,
    PaperResearchCard,
)
from research_lab.research_card_backfill import backfill_research_cards


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    for table in (
        Paper.__table__,
        PaperChunk.__table__,
        PaperResearchCard.__table__,
        CitationSnapshot.__table__,
        EvidenceClaim.__table__,
        EvidenceLink.__table__,
    ):
        table.create(engine)
    return Session(engine)


def _paper(title: str, *, year: int, source_record_id: str) -> Paper:
    return Paper(
        title=title,
        abstract=(
            "This study examines artificial intelligence capability and firm performance. "
            "Drawing on dynamic capabilities, we use a longitudinal panel dataset and econometric "
            "fixed effects models. A limitation is causal identification and external validity. "
            "Future research should test the mechanism across industries and countries."
        ),
        publication_year=year,
        primary_source="test",
        source_record_id=source_record_id,
        retrieved_at=datetime.now(UTC),
        provenance={},
    )


def _chunk(paper: Paper, text: str, page: int = 1) -> PaperChunk:
    return PaperChunk(
        paper_id=paper.id,
        source_locator=f"page:{page}",
        text=text,
        text_hash=sha256(text.encode()).hexdigest(),
        page_start=page,
        page_end=page,
        char_start=0,
        char_end=len(text),
    )


def test_backfill_research_cards_prioritizes_cited_full_text_papers_and_creates_evidence() -> None:
    with _session() as session:
        high = _paper("Highly cited AI capability paper", year=2024, source_record_id="high")
        low = _paper("Lower cited AI adoption paper", year=2025, source_record_id="low")
        no_full_text = _paper("Metadata only paper", year=2026, source_record_id="metadata")
        session.add_all([high, low, no_full_text])
        session.flush()
        session.add_all(
            [
                _chunk(
                    high,
                    "The research question asks how AI capability improves firm performance. "
                    "The methodology uses fixed effects on panel data.",
                ),
                _chunk(low, "The limitation is a single-country survey sample."),
                CitationSnapshot(
                    paper_id=high.id,
                    source="test",
                    citation_count=100,
                    captured_at=datetime.now(UTC),
                ),
                CitationSnapshot(
                    paper_id=low.id,
                    source="test",
                    citation_count=5,
                    captured_at=datetime.now(UTC),
                ),
            ]
        )
        session.commit()

        dry_run = backfill_research_cards(session, limit=1, dry_run=True)
        assert dry_run.selected == 1
        assert dry_run.created == 0

        result = backfill_research_cards(session, limit=1)

        assert result.selected == 1
        assert result.created == 1
        assert result.evidence_claims_created > 0
        assert result.evidence_links_created == result.evidence_claims_created
        card = session.query(PaperResearchCard).one()
        assert card.paper_id == high.id
        assert "methodology" in card.fields
        assert session.query(EvidenceClaim).count() == result.evidence_claims_created
        assert session.query(EvidenceLink).count() == result.evidence_links_created


def test_backfill_research_cards_is_idempotent() -> None:
    with _session() as session:
        paper = _paper("AI governance paper", year=2025, source_record_id="idempotent")
        session.add(paper)
        session.flush()
        session.add(_chunk(paper, "This paper examines governance limitations and future research."))
        session.commit()

        first = backfill_research_cards(session, limit=10)
        second = backfill_research_cards(session, limit=10)

        assert first.created == 1
        assert second.created == 0
        assert session.query(PaperResearchCard).count() == 1

