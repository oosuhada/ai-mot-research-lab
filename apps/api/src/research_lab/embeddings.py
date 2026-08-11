from __future__ import annotations

import hashlib
import importlib
import math
import re
from typing import Any, Protocol

from research_lab.config import Settings

TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9\-]{1,}")


class EmbeddingProvider(Protocol):
    name: str
    model: str
    dimensions: int

    def embed_query(self, text: str) -> list[float]: ...
    def embed_document(self, text: str) -> list[float]: ...


class LocalHashEmbeddingProvider:
    """Deterministic no-key vector baseline for development and contract tests.

    It intentionally does not claim neural semantic quality. It keeps the pgvector/hybrid path usable
    without a commercial key so the retrieval contract can still be tested end to end.
    """

    name = "local_hash"
    model = "token-hash-v1"
    dimensions = 384

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = TOKEN_PATTERN.findall(text.lower())

        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=16).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        magnitude = math.sqrt(sum(value * value for value in vector))
        if magnitude == 0.0:
            return vector
        return [value / magnitude for value in vector]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def embed_document(self, text: str) -> list[float]:
        return self._embed(text)


class FastEmbedEmbeddingProvider:
    """Optional neural local embedding provider backed by FastEmbed/ONNX.

    The provider is lazy so importing the API does not download a model or require the optional
    dependency. The configured model must emit 384-dimensional vectors because the current pgvector
    schema is fixed to 384 dimensions.
    """

    name = "fastembed"
    dimensions = 384

    def __init__(self, model: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        self.model = model
        self._backend: Any | None = None

    def _load_backend(self) -> Any:
        if self._backend is not None:
            return self._backend
        try:
            module = importlib.import_module("fastembed")
        except ImportError as exc:
            raise RuntimeError(
                "FastEmbed is not installed. Install the API `local-embeddings` extra first."
            ) from exc
        backend = module.TextEmbedding(model_name=self.model)
        self._backend = backend
        return backend

    def _coerce_vector(self, vector: Any) -> list[float]:
        values = [float(value) for value in vector]
        if len(values) != self.dimensions:
            raise RuntimeError(
                f"Embedding model {self.model!r} emitted {len(values)} dimensions; expected {self.dimensions}."
            )
        return values

    def embed_query(self, text: str) -> list[float]:
        backend = self._load_backend()
        return self._coerce_vector(next(iter(backend.query_embed(text))))

    def embed_document(self, text: str) -> list[float]:
        backend = self._load_backend()
        return self._coerce_vector(next(iter(backend.passage_embed([text]))))


def build_embedding_provider(settings: Settings, provider_name: str | None = None) -> EmbeddingProvider:
    selected = (provider_name or settings.embedding_provider).strip().lower()
    if selected == "local_hash":
        return LocalHashEmbeddingProvider()
    if selected == "fastembed":
        return FastEmbedEmbeddingProvider(settings.fastembed_model)
    raise ValueError(f"Unknown embedding provider: {selected}")

