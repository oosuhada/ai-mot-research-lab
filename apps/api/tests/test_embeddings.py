from __future__ import annotations

from research_lab.config import Settings
from research_lab.embeddings import FastEmbedEmbeddingProvider, LocalHashEmbeddingProvider, build_embedding_provider


def test_embedding_provider_factory_preserves_no_download_default() -> None:
    provider = build_embedding_provider(Settings(_env_file=None))
    assert isinstance(provider, LocalHashEmbeddingProvider)


def test_fastembed_provider_is_lazy() -> None:
    provider = FastEmbedEmbeddingProvider()
    assert provider.name == "fastembed"
    assert provider.dimensions == 384
    assert provider._backend is None
