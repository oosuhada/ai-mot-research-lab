from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from research_lab.embeddings import EmbeddingProvider
from research_lab.models import Paper, PaperChunk, PaperEmbedding


@dataclass(frozen=True, slots=True)
class EmbeddingBackfillResult:
    papers_processed: int
    paper_embeddings_inserted: int
    paper_embeddings_updated: int
    chunks_updated: int


def backfill_embeddings(
    session: Session,
    provider: EmbeddingProvider,
) -> EmbeddingBackfillResult:
    papers = session.scalars(select(Paper).order_by(Paper.id)).all()
    inserted = 0
    updated = 0
    for paper in papers:
        text = f"{paper.title}\n{paper.abstract or ''}".strip()
        vector = provider.embed(text)
        row = session.scalar(
            select(PaperEmbedding).where(
                PaperEmbedding.paper_id == paper.id,
                PaperEmbedding.provider == provider.name,
                PaperEmbedding.model == provider.model,
            )
        )
        if row is None:
            session.add(
                PaperEmbedding(
                    paper_id=paper.id,
                    provider=provider.name,
                    model=provider.model,
                    dimensions=provider.dimensions,
                    embedding=vector,
                )
            )
            inserted += 1
        else:
            row.embedding = vector
            row.dimensions = provider.dimensions
            updated += 1

    chunks = session.scalars(select(PaperChunk).order_by(PaperChunk.id)).all()
    for chunk in chunks:
        chunk.embedding = provider.embed(chunk.text)

    session.commit()
    return EmbeddingBackfillResult(
        papers_processed=len(papers),
        paper_embeddings_inserted=inserted,
        paper_embeddings_updated=updated,
        chunks_updated=len(chunks),
    )
