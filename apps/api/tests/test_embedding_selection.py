from __future__ import annotations

from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from research_lab.config import Settings
from research_lab.embedding_selection import choose_search_embedding_provider


def test_auto_selects_fastembed_only_with_complete_matching_coverage() -> None:
    session = MagicMock(spec=Session)
    session.scalar.side_effect = [529, 529]

    with patch("research_lab.embedding_selection.importlib.util.find_spec", return_value=object()):
        selection = choose_search_embedding_provider(session, Settings(_env_file=None), "auto")

    assert selection.provider.name == "fastembed"
    assert selection.reason == "complete_fastembed_corpus_coverage"
    assert selection.canonical_papers == 529
    assert selection.matching_embeddings == 529


def test_auto_falls_back_when_fastembed_coverage_is_partial() -> None:
    session = MagicMock(spec=Session)
    session.scalar.side_effect = [529, 528, 529]

    with patch("research_lab.embedding_selection.importlib.util.find_spec", return_value=object()):
        selection = choose_search_embedding_provider(session, Settings(_env_file=None), "auto")

    assert selection.provider.name == "local_hash"
    assert selection.reason == "fallback_local_hash_fastembed_not_fully_ready"
    assert selection.matching_embeddings == 529


def test_explicit_provider_is_not_overridden_by_auto_policy() -> None:
    session = MagicMock(spec=Session)
    session.scalar.side_effect = [529, 529]

    selection = choose_search_embedding_provider(session, Settings(_env_file=None), "local_hash")

    assert selection.provider.name == "local_hash"
    assert selection.reason == "explicit_user_selection"
