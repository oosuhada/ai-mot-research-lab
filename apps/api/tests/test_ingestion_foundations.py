from __future__ import annotations

import httpx
import pytest
from pydantic import ValidationError

from research_lab.embeddings import LocalHashEmbeddingProvider
from research_lab.ingestion.http import ResilientHttpClient
from research_lab.ingestion.normalization import normalize_doi, normalize_openalex_id
from research_lab.ingestion.openalex import reconstruct_abstract
from research_lab.schemas import EvidenceClaimCreate
from research_lab.taxonomy import AXIS_BY_SLUG, text_matches_axis


def test_identifier_normalization_is_stable() -> None:
    assert normalize_doi("https://doi.org/10.1000/ABC") == "10.1000/abc"
    assert normalize_doi("doi: 10.1000/abc") == "10.1000/abc"
    assert normalize_openalex_id("https://openalex.org/W123") == "W123"


def test_openalex_abstract_is_reconstructed_by_position() -> None:
    abstract = reconstruct_abstract({"AI": [0], "changes": [1], "work": [2]})
    assert abstract == "AI changes work"


def test_axis_filter_requires_ai_and_management_context() -> None:
    axis = AXIS_BY_SLUG["ai-adoption-business-value"]
    assert text_matches_axis("Artificial intelligence adoption improves firm performance", axis)
    assert not text_matches_axis("Transformer benchmark accuracy improves by two points", axis)


def test_local_hash_embedding_is_deterministic_and_normalized() -> None:
    provider = LocalHashEmbeddingProvider()
    first = provider.embed("AI adoption and firm performance")
    second = provider.embed("AI adoption and firm performance")

    assert first == second
    assert len(first) == 384
    assert sum(value * value for value in first) == pytest.approx(1.0)


def test_retry_honors_retry_after_and_eventually_succeeds() -> None:
    calls = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "2"}, request=request)
        return httpx.Response(200, json={"ok": True}, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    resilient = ResilientHttpClient(client, jitter_ratio=0.0, sleeper=sleeps.append)

    assert resilient.get_json("https://example.test/data") == {"ok": True}
    assert calls == 2
    assert sleeps == [2.0]


def test_retry_does_not_hide_deterministic_client_error() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(400, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    resilient = ResilientHttpClient(client, sleeper=lambda _: None)

    with pytest.raises(httpx.HTTPStatusError):
        resilient.get_json("https://example.test/data")
    assert calls == 1


def test_supported_evidence_claim_cannot_exist_without_evidence_link() -> None:
    with pytest.raises(ValidationError):
        EvidenceClaimCreate(
            claim_text="AI adoption improves performance.",
            claim_kind="system_inference",
            support_status="supported",
            evidence=[],
        )

    claim = EvidenceClaimCreate(
        claim_text="The corpus does not contain enough evidence.",
        claim_kind="system_inference",
        support_status="insufficient_evidence",
        evidence=[],
    )
    assert claim.support_status == "insufficient_evidence"

