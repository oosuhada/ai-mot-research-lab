from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from research_lab.embeddings import EmbeddingProvider
from research_lab.models import Paper, PaperChunk, PaperEmbedding


@dataclass(frozen=True, slots=True)
class EmbeddingBackfillResult:
    papers_processed: int
    paper_embeddings_inserted: int
    paper_embeddings_updated: int
    chunks_updated: int
    papers_skipped: int


def backfill_embeddings(
    session: Session,
    provider: EmbeddingProvider,
    *,
    batch_size: int = 100,
    only_missing: bool = False,
    include_chunks: bool = False,
) -> EmbeddingBackfillResult:
    total_papers = int(session.scalar(select(func.count()).select_from(Paper)) or 0)
    inserted = 0
    updated = 0
    skipped = 0
    effective_batch_size = max(1, batch_size)
    last_id = None
    while True:
        statement = select(Paper).order_by(Paper.id).limit(effective_batch_size)
        if last_id is not None:
            statement = statement.where(Paper.id > last_id)
        papers = session.scalars(statement).all()
        if not papers:
            break
        for paper in papers:
            row = session.scalar(
                select(PaperEmbedding).where(
                    PaperEmbedding.paper_id == paper.id,
                    PaperEmbedding.provider == provider.name,
                    PaperEmbedding.model == provider.model,
                )
            )
            if row is not None and only_missing:
                skipped += 1
                continue
            # Abstracts are embedded immediately; title is retained as a stable fallback
            # for records whose rights/metadata source does not provide an abstract.
            document = f"{paper.title}\n{paper.abstract or ''}".strip()
            vector = provider.embed_document(document)
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
        last_id = papers[-1].id
        session.commit()

    chunks = session.scalars(select(PaperChunk).order_by(PaperChunk.id)).all() if include_chunks else []
    for chunk in chunks:
        if (
            only_missing
            and chunk.embedding is not None
            and chunk.embedding_provider == provider.name
            and chunk.embedding_model == provider.model
        ):
            continue
        chunk.embedding = provider.embed_document(chunk.text)
        chunk.embedding_provider = provider.name
        chunk.embedding_model = provider.model

    session.commit()
    return EmbeddingBackfillResult(
        papers_processed=total_papers,
        paper_embeddings_inserted=inserted,
        paper_embeddings_updated=updated,
        chunks_updated=len(chunks),
        papers_skipped=skipped,
    )
