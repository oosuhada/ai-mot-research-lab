from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9\-]{1,}")


class EmbeddingProvider(Protocol):
    name: str
    model: str
    dimensions: int

    def embed(self, text: str) -> list[float]: ...


class LocalHashEmbeddingProvider:
    """Deterministic no-key vector baseline for development and contract tests.

    It intentionally does not claim neural semantic quality. It keeps the pgvector/hybrid path usable
    without a commercial key so the retrieval contract can still be tested end to end.
    """

    name = "local_hash"
    model = "token-hash-v1"
    dimensions = 384

    def embed(self, text: str) -> list[float]:
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

