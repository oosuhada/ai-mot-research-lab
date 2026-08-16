from __future__ import annotations

from datetime import UTC, date, datetime

import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from research_lab.config import Settings
from research_lab.embeddings import LocalHashEmbeddingProvider
from research_lab.ingestion.http import ResilientHttpClient
from research_lab.ingestion.normalization import normalize_arxiv_id, normalize_doi, normalize_openalex_id
from research_lab.ingestion.openalex import OpenAlexClient, reconstruct_abstract
from research_lab.ingestion.service import OpenAlexIngestionService
from research_lab.models import Author, Paper, PaperAuthor, Venue
from research_lab.schemas import EvidenceClaimCreate
from research_lab.taxonomy import AXIS_BY_SLUG, infer_subaxis_labels, text_matches_axis


class _NoopOpenAlexClient:
    def close(self) -> None:
        return None


@pytest.fixture
def ingestion_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    for table in (Venue.__table__, Author.__table__, Paper.__table__, PaperAuthor.__table__):
        table.create(engine)
    with Session(engine) as session:
        yield session


def _ingestion_service(session: Session) -> OpenAlexIngestionService:
    return OpenAlexIngestionService(
        session,
        Settings(database_url="sqlite+pysqlite:///:memory:"),
        client=_NoopOpenAlexClient(),  # type: ignore[arg-type]
        embedding_provider=LocalHashEmbeddingProvider(),
        preload_caches=False,
    )


def _paper(session: Session, source_record_id: str = "W-PAPER-1") -> Paper:
    paper = Paper(
        title="Canonical paper",
        primary_source="openalex",
        source_record_id=source_record_id,
        retrieved_at=datetime.now(UTC),
        provenance={},
    )
    session.add(paper)
    session.flush()
    return paper


def _authorship(openalex_id: str, *, orcid: str | None, name: str = "Researcher") -> dict[str, object]:
    return {
        "author": {
            "id": f"https://openalex.org/{openalex_id}",
            "orcid": f"https://orcid.org/{orcid}" if orcid else None,
            "display_name": name,
        },
        "raw_affiliation_strings": [],
        "institutions": [],
        "is_corresponding": False,
    }


def test_identifier_normalization_is_stable() -> None:
    assert normalize_doi("https://doi.org/10.1000/ABC") == "10.1000/abc"
    assert normalize_doi("doi: 10.1000/abc") == "10.1000/abc"
    assert normalize_openalex_id("https://openalex.org/W123") == "W123"
    assert normalize_arxiv_id("https://arxiv.org/abs/2401.12345v2") == "2401.12345"
    assert normalize_arxiv_id("arXiv: 2401.12345") == "2401.12345"


def test_adoption_subaxis_labels_keep_the_broad_axis_auditable() -> None:
    labels = infer_subaxis_labels(
        "We examine AI capability, workflow redesign, and return on investment in manufacturing firms."
    )

    assert "ai-capability-development" in labels
    assert "workflow-transformation" in labels
    assert "value-roi" in labels


def test_openalex_abstract_is_reconstructed_by_position() -> None:
    abstract = reconstruct_abstract({"AI": [0], "changes": [1], "work": [2]})
    assert abstract == "AI changes work"


def test_daily_openalex_window_uses_independent_publication_date_filter() -> None:
    captured_query = ""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_query
        captured_query = request.url.query.decode()
        return httpx.Response(200, json={"meta": {"count": 0}, "results": []}, request=request)

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = OpenAlexClient(
        Settings(openalex_base_url="https://api.openalex.test"),
        client=http_client,
    )
    records, total = client.fetch_axis_date_page(
        AXIS_BY_SLUG["ai-adoption-business-value"],
        from_date=date(2026, 8, 22),
        to_date=date(2026, 8, 24),
        page=1,
    )

    assert records == []
    assert total == 0
    assert "from_publication_date%3A2026-08-22" in captured_query
    assert "to_publication_date%3A2026-08-24" in captured_query
    assert "sort=publication_date%3Adesc" in captured_query


def test_axis_filter_requires_ai_and_management_context() -> None:
    axis = AXIS_BY_SLUG["ai-adoption-business-value"]
    assert text_matches_axis("Artificial intelligence adoption improves firm performance", axis)
    assert not text_matches_axis("Transformer benchmark accuracy improves by two points", axis)


def test_local_hash_embedding_is_deterministic_and_normalized() -> None:
    provider = LocalHashEmbeddingProvider()
    first = provider.embed_document("AI adoption and firm performance")
    second = provider.embed_document("AI adoption and firm performance")

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


def test_same_openalex_author_reingestion_reuses_one_author(ingestion_session: Session) -> None:
    service = _ingestion_service(ingestion_session)
    paper = _paper(ingestion_session)
    authorships = [_authorship("A100", orcid="0000-0001-7409-5813")]

    service._replace_openalex_authorships(paper, authorships)
    service._replace_openalex_authorships(paper, authorships)
    ingestion_session.flush()

    assert ingestion_session.scalar(select(func.count()).select_from(Author)) == 1
    assert ingestion_session.scalar(select(func.count()).select_from(PaperAuthor)) == 1


def test_different_openalex_ids_with_same_orcid_reuse_canonical_author(ingestion_session: Session) -> None:
    service = _ingestion_service(ingestion_session)
    first_paper = _paper(ingestion_session, "W-PAPER-1")
    second_paper = _paper(ingestion_session, "W-PAPER-2")

    service._replace_openalex_authorships(
        first_paper,
        [_authorship("A100", orcid="0000-0001-7409-5813", name="Canonical Name")],
    )
    service._replace_openalex_authorships(
        second_paper,
        [_authorship("A200", orcid="0000-0001-7409-5813", name="Provider Variant")],
    )
    ingestion_session.flush()

    authors = list(ingestion_session.scalars(select(Author)))
    assert len(authors) == 1
    assert authors[0].openalex_id == "A100"
    assert authors[0].display_name == "Canonical Name"
    assert service.authors_by_openalex["A200"].id == authors[0].id
    assert ingestion_session.scalar(select(func.count()).select_from(PaperAuthor)) == 2


def test_author_without_orcid_is_keyed_by_openalex_id(ingestion_session: Session) -> None:
    service = _ingestion_service(ingestion_session)
    first_paper = _paper(ingestion_session, "W-PAPER-1")
    second_paper = _paper(ingestion_session, "W-PAPER-2")

    service._replace_openalex_authorships(first_paper, [_authorship("A100", orcid=None)])
    service._replace_openalex_authorships(second_paper, [_authorship("A200", orcid=None)])
    ingestion_session.flush()

    assert ingestion_session.scalar(select(func.count()).select_from(Author)) == 2


def test_existing_orcid_author_without_openalex_id_is_safely_enriched(ingestion_session: Session) -> None:
    canonical = Author(
        openalex_id=None,
        orcid="0000-0001-7409-5813",
        display_name="Existing Canonical Name",
    )
    ingestion_session.add(canonical)
    ingestion_session.flush()
    service = _ingestion_service(ingestion_session)
    paper = _paper(ingestion_session)

    service._replace_openalex_authorships(
        paper,
        [_authorship("A100", orcid="0000-0001-7409-5813", name="Incoming Name")],
    )
    ingestion_session.flush()

    ingestion_session.refresh(canonical)
    assert canonical.openalex_id == "A100"
    assert canonical.display_name == "Existing Canonical Name"
    assert ingestion_session.scalar(select(func.count()).select_from(Author)) == 1


def test_same_paper_reprocessing_does_not_duplicate_author_links(ingestion_session: Session) -> None:
    service = _ingestion_service(ingestion_session)
    paper = _paper(ingestion_session)
    first = _authorship("A100", orcid="0000-0001-7409-5813")
    first["raw_affiliation_strings"] = ["Lab A"]
    second = _authorship("A100", orcid="0000-0001-7409-5813")
    second["raw_affiliation_strings"] = ["Lab A", "Lab B"]

    service._replace_openalex_authorships(paper, [first])
    service._replace_openalex_authorships(paper, [second])
    ingestion_session.flush()

    rows = list(ingestion_session.scalars(select(PaperAuthor)))
    assert len(rows) == 1
    assert rows[0].raw_affiliation == "Lab A; Lab B"
