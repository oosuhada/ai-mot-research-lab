from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal

from fastapi import HTTPException
from sqlalchemy import exists, func, select, update
from sqlalchemy.orm import Session

from research_lab.models import Citation, CitationSnapshot, Paper
from research_lab.schemas import CitationNeighbor, CitationSnowballResponse


@dataclass(frozen=True, slots=True)
class CitationResolutionResult:
    matched_edges: int
    remaining_external_edges: int


def resolve_local_citation_edges(session: Session) -> CitationResolutionResult:
    """Connect OpenAlex external citation IDs to canonical papers already in the local corpus."""
    matching_paper_id = (
        select(Paper.id)
        .where(Paper.openalex_id == Citation.cited_external_id)
        .limit(1)
        .scalar_subquery()
    )
    has_local_match = exists(
        select(Paper.id).where(Paper.openalex_id == Citation.cited_external_id)
    )
    result = session.execute(
        update(Citation)
        .where(
            Citation.cited_paper_id.is_(None),
            Citation.cited_external_id.is_not(None),
            has_local_match,
        )
        .values(cited_paper_id=matching_paper_id)
        .execution_options(synchronize_session=False)
    )
    session.commit()
    remaining = session.scalar(
        select(func.count()).select_from(Citation).where(Citation.cited_paper_id.is_(None))
    ) or 0
    return CitationResolutionResult(
        matched_edges=max(int(result.rowcount or 0), 0),
        remaining_external_edges=int(remaining),
    )


def get_snowball_neighbors(
    session: Session,
    paper_id: uuid.UUID,
    *,
    backward_limit: int = 20,
    forward_limit: int = 20,
) -> CitationSnowballResponse:
    paper = session.get(Paper, paper_id)
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found")

    backward = session.execute(
        select(Paper, Citation)
        .join(Citation, Citation.cited_paper_id == Paper.id)
        .where(Citation.citing_paper_id == paper_id)
        .order_by(Paper.publication_year.desc().nullslast(), Paper.title)
        .limit(backward_limit)
    ).all()
    forward = session.execute(
        select(Paper, Citation)
        .join(Citation, Citation.citing_paper_id == Paper.id)
        .where(Citation.cited_paper_id == paper_id)
        .order_by(Paper.publication_year.desc().nullslast(), Paper.title)
        .limit(forward_limit)
    ).all()

    return CitationSnowballResponse(
        paper_id=paper.id,
        paper_title=paper.title,
        backward=[_neighbor(session, cited, edge, direction="backward") for cited, edge in backward],
        forward=[_neighbor(session, citing, edge, direction="forward") for citing, edge in forward],
    )


def _neighbor(
    session: Session,
    paper: Paper,
    edge: Citation,
    *,
    direction: Literal["backward", "forward"],
) -> CitationNeighbor:
    citation_count = session.scalar(
        select(CitationSnapshot.citation_count)
        .where(CitationSnapshot.paper_id == paper.id)
        .order_by(CitationSnapshot.captured_at.desc())
        .limit(1)
    )
    return CitationNeighbor(
        id=paper.id,
        title=paper.title,
        doi=paper.doi,
        publication_year=paper.publication_year,
        primary_url=paper.primary_url,
        direction=direction,
        source=edge.source,
        citation_count=citation_count,
    )
