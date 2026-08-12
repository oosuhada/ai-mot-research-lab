from __future__ import annotations

import importlib
from dataclasses import replace
from functools import lru_cache
from typing import Any

from research_lab.config import Settings
from research_lab.retrieval import RankedPaper


class FastEmbedCrossEncoderReranker:
    """Optional local cross-encoder reranker over an already retrieved candidate set."""

    name = "fastembed_cross_encoder"

    def __init__(self, model: str = "Xenova/ms-marco-MiniLM-L-6-v2") -> None:
        self.model = model
        self._backend: Any | None = None

    def _load_backend(self) -> Any:
        if self._backend is not None:
            return self._backend
        try:
            module = importlib.import_module("fastembed.rerank.cross_encoder")
        except ImportError as exc:
            raise RuntimeError(
                "FastEmbed is not installed. Install the API `local-embeddings` extra before reranking."
            ) from exc
        backend = module.TextCrossEncoder(model_name=self.model)
        self._backend = backend
        return backend

    def rerank(self, query: str, rows: list[RankedPaper], *, limit: int) -> list[RankedPaper]:
        if not rows:
            return []
        documents = [
            f"{row.title}\n{row.matched_excerpt or row.abstract or ''}".strip()
            for row in rows
        ]
        scores = [float(score) for score in self._load_backend().rerank(query, documents)]
        scored = [replace(row, rerank_score=score) for row, score in zip(rows, scores, strict=True)]
        scored.sort(
            key=lambda row: (
                -(row.rerank_score if row.rerank_score is not None else float("-inf")),
                -row.fused_score,
                str(row.id),
            )
        )
        return scored[:limit]


def build_reranker(settings: Settings, reranker_name: str) -> FastEmbedCrossEncoderReranker | None:
    selected = reranker_name.strip().lower()
    if selected == "none":
        return None
    if selected == "fastembed":
        return _cached_fastembed_reranker(settings.fastembed_reranker_model)
    raise ValueError(f"Unknown reranker: {selected}")


@lru_cache(maxsize=4)
def _cached_fastembed_reranker(model: str) -> FastEmbedCrossEncoderReranker:
    return FastEmbedCrossEncoderReranker(model)
