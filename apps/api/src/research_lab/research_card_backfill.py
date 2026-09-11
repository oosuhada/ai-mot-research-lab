from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass

from sqlalchemy import desc, exists, func, select
from sqlalchemy.orm import Session

from research_lab.models import (
    CitationSnapshot,
    EvidenceClaim,
    EvidenceLink,
    Paper,
    PaperChunk,
    PaperResearchCard,
)
from research_lab.research_workflow import (
    RESEARCH_CARD_VERSION,
    _extract_candidate_fields,
)
from research_lab.schemas import ResearchCardField


@dataclass(frozen=True, slots=True)
class ResearchCardBackfillResult:
    selected: int
    created: int
    skipped_existing: int
    skipped_missing_paper: int
    evidence_claims_created: int
    evidence_links_created: int
    dry_run: bool = False

    def asdict(self) -> dict[str, int | bool]:
        return asdict(self)


def backfill_research_cards(
    session: Session,
    *,
    limit: int = 100,
    min_year: int | None = None,
    create_evidence_claims: bool = True,
    dry_run: bool = False,
    commit_every: int = 25,
) -> ResearchCardBackfillResult:
    """Materialize heuristic Research Cards for high-signal full-text papers.

    The extractor is intentionally conservative: it only stores fields with
    explicit abstract/chunk locators and marks everything else as insufficient
    evidence. This makes the batch safe to run automatically while preserving
    the human-review boundary in the UI.
    """

    paper_ids = _candidate_paper_ids(session, limit=max(limit, 1), min_year=min_year)
    if dry_run:
        return ResearchCardBackfillResult(
            selected=len(paper_ids),
            created=0,
            skipped_existing=0,
            skipped_missing_paper=0,
            evidence_claims_created=0,
            evidence_links_created=0,
            dry_run=True,
        )

    created = 0
    skipped_existing = 0
    skipped_missing = 0
    claim_count = 0
    link_count = 0
    commit_every = max(commit_every, 1)

    for index, paper_id in enumerate(paper_ids, start=1):
        if session.scalar(select(PaperResearchCard.id).where(PaperResearchCard.paper_id == paper_id)):
            skipped_existing += 1
            continue

        paper = session.get(Paper, paper_id)
        if paper is None:
            skipped_missing += 1
            continue

        fields, _evidence_depth = _extract_candidate_fields(session, paper)
        card = PaperResearchCard(
            paper_id=paper.id,
            status="candidate",
            extraction_version=RESEARCH_CARD_VERSION,
            fields={key: value.model_dump(mode="json") for key, value in fields.items()},
        )
        session.add(card)
        session.flush()
        created += 1

        if create_evidence_claims:
            card_claims, card_links = _create_card_evidence_claims(session, card, paper.id, fields)
            claim_count += card_claims
            link_count += card_links

        if index % commit_every == 0:
            session.commit()

    session.commit()
    return ResearchCardBackfillResult(
        selected=len(paper_ids),
        created=created,
        skipped_existing=skipped_existing,
        skipped_missing_paper=skipped_missing,
        evidence_claims_created=claim_count,
        evidence_links_created=link_count,
    )


def _candidate_paper_ids(session: Session, *, limit: int, min_year: int | None) -> list[uuid.UUID]:
    latest_citations = (
        select(
            CitationSnapshot.paper_id.label("paper_id"),
            func.max(CitationSnapshot.citation_count).label("citation_count"),
        )
        .group_by(CitationSnapshot.paper_id)
        .subquery()
    )
    conditions = [
        exists(select(1).where(PaperChunk.paper_id == Paper.id)),
        ~exists(select(1).where(PaperResearchCard.paper_id == Paper.id)),
    ]
    if min_year is not None:
        conditions.append(Paper.publication_year >= min_year)

    rows = session.scalars(
        select(Paper.id)
        .outerjoin(latest_citations, latest_citations.c.paper_id == Paper.id)
        .where(*conditions)
        .order_by(
            desc(func.coalesce(latest_citations.c.citation_count, 0)),
            desc(func.coalesce(Paper.publication_year, 0)),
            Paper.id,
        )
        .limit(limit)
    ).all()
    return list(rows)


def _create_card_evidence_claims(
    session: Session,
    card: PaperResearchCard,
    paper_id: uuid.UUID,
    fields: dict[str, ResearchCardField],
) -> tuple[int, int]:
    claim_count = 0
    link_count = 0
    for field_name, field in fields.items():
        value_text = (field.value_text or "").strip()
        if not value_text or field.support_status != "supported" or not field.source_locator:
            continue
        claim = EvidenceClaim(
            claim_text=_claim_text(field_name, value_text),
            claim_kind="paper_claim" if field.origin == "paper_evidence" else "system_inference",
            support_status="supported",
            scope_type="paper_research_card",
            scope_id=card.id,
        )
        session.add(claim)
        session.flush()
        claim_count += 1
        session.add(
            EvidenceLink(
                claim_id=claim.id,
                paper_id=paper_id,
                chunk_id=field.chunk_id,
                relation="supports",
                source_locator=field.source_locator,
            )
        )
        link_count += 1
    return claim_count, link_count


def _claim_text(field_name: str, value_text: str) -> str:
    label = field_name.replace("_", " ")
    compact = " ".join(value_text.split())
    if len(compact) > 700:
        compact = compact[:697].rstrip() + "..."
    return f"Research card {label}: {compact}"

