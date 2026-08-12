from research_lab.config import Settings
from research_lab.reranking import FastEmbedCrossEncoderReranker, build_reranker


def test_reranker_factory_preserves_no_download_default() -> None:
    assert build_reranker(Settings(_env_file=None), "none") is None


def test_fastembed_reranker_is_lazy() -> None:
    reranker = FastEmbedCrossEncoderReranker()
    assert reranker.name == "fastembed_cross_encoder"
    assert reranker._backend is None


def test_fastembed_reranker_factory_reuses_process_level_instance() -> None:
    settings = Settings(_env_file=None)
    assert build_reranker(settings, "fastembed") is build_reranker(settings, "fastembed")
