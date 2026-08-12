from __future__ import annotations

import importlib.util
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from research_lab.config import Settings
from research_lab.embeddings import EmbeddingProvider, build_embedding_provider
from research_lab.models import Paper, PaperEmbedding


@dataclass(frozen=True, slots=True)
class EmbeddingSelection:
    provider: EmbeddingProvider
    requested: str
    reason: str
    canonical_papers: int
    matching_embeddings: int


def choose_search_embedding_provider(
    session: Session,
    settings: Settings,
    requested: str,
) -> EmbeddingSelection:
    selected = requested.strip().lower()
    if selected != "auto":
        provider = build_embedding_provider(settings, selected)
        return EmbeddingSelection(
            provider=provider,
            requested=selected,
            reason="explicit_user_selection",
            canonical_papers=_paper_count(session),
            matching_embeddings=_embedding_count(session, provider.name, provider.model),
        )

    canonical_papers = _paper_count(session)
    fastembed_count = _embedding_count(session, "fastembed", settings.fastembed_model)
    fastembed_installed = importlib.util.find_spec("fastembed") is not None
    if canonical_papers > 0 and fastembed_count == canonical_papers and fastembed_installed:
        provider = build_embedding_provider(settings, "fastembed")
        return EmbeddingSelection(
            provider=provider,
            requested="auto",
            reason="complete_fastembed_corpus_coverage",
            canonical_papers=canonical_papers,
            matching_embeddings=fastembed_count,
        )

    provider = build_embedding_provider(settings, "local_hash")
    return EmbeddingSelection(
        provider=provider,
        requested="auto",
        reason=(
            "fallback_local_hash_fastembed_not_fully_ready"
            if canonical_papers
            else "fallback_local_hash_empty_corpus"
        ),
        canonical_papers=canonical_papers,
        matching_embeddings=_embedding_count(session, provider.name, provider.model),
    )


def _paper_count(session: Session) -> int:
    return int(session.scalar(select(func.count()).select_from(Paper)) or 0)


def _embedding_count(session: Session, provider: str, model: str) -> int:
    return int(
        session.scalar(
            select(func.count()).select_from(PaperEmbedding).where(
                PaperEmbedding.provider == provider,
                PaperEmbedding.model == model,
            )
        )
        or 0
    )
