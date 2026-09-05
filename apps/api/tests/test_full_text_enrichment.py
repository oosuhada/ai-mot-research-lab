from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from research_lab.config import Settings
from research_lab.full_text_enrichment import FullTextEnrichmentWorker
from research_lab.full_text_provenance import backfill_full_text_provenance
from research_lab.full_text_sources import (
    ArxivResolver,
    CoreSourceResolver,
    EuropePmcSourceResolver,
    OpenAccessSourceResolver,
    PreprintSourceResolver,
    UnpaywallSourceResolver,
)
from research_lab.models import (
    FullTextQueueItem,
    FullTextSourceAttempt,
    IngestionRun,
    Paper,
    PaperChunk,
    PaperContentProfile,
    PaperVersion,
)
from research_lab.pdf_pipeline import PdfEvidenceService
from research_lab.xml_pipeline import XmlEvidenceService


def test_full_text_worker_processes_only_rights_safe_queue_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    for table in (
        Paper.__table__,
        PaperContentProfile.__table__,
        FullTextQueueItem.__table__,
        FullTextSourceAttempt.__table__,
    ):
        table.create(engine)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"%PDF-1.7\nqueue-test", request=request)

    captured_ingest_kwargs: dict[str, object] = {}

    def fake_ingest(*_args: object, **kwargs: object) -> object:
        captured_ingest_kwargs.update(kwargs)
        return SimpleNamespace(chunk_count=4, extraction_status="extracted")

    monkeypatch.setattr(PdfEvidenceService, "ingest", fake_ingest)
    with Session(engine) as session:
        eligible = Paper(
            title="Open paper",
            is_oa=True,
            pdf_url="https://example.test/open.pdf",
            primary_source="openalex",
            source_record_id="W-OPEN",
            retrieved_at=datetime.now(timezone.utc),
            provenance={},
        )
        restricted = Paper(
            title="Restricted paper",
            is_oa=False,
            primary_source="openalex",
            source_record_id="W-CLOSED",
            retrieved_at=datetime.now(timezone.utc),
            provenance={},
        )
        session.add_all([eligible, restricted])
        session.flush()
        eligible_profile = PaperContentProfile(paper_id=eligible.id, full_text_status="queued")
        restricted_profile = PaperContentProfile(paper_id=restricted.id, full_text_status="restricted")
        eligible_queue = FullTextQueueItem(
            paper_id=eligible.id,
            priority=90,
            status="pending",
            rights_status="open_access",
        )
        restricted_queue = FullTextQueueItem(
            paper_id=restricted.id,
            priority=100,
            status="pending",
            rights_status="restricted",
        )
        session.add_all([eligible_profile, restricted_profile, eligible_queue, restricted_queue])
        session.commit()

        result = FullTextEnrichmentWorker(
            session,
            Settings(database_url="sqlite+pysqlite:///:memory:"),
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        ).run(max_items=3)

        session.refresh(eligible_queue)
        session.refresh(restricted_queue)
        session.refresh(eligible_profile)
        assert result["selected"] == 1
        assert result["completed"] == 1
        assert result["failed"] == 0
        assert result["deferred"] == 0
        assert result["stale_leases_recovered"] == 0
        assert result["legacy_failures_requeued"] == 0
        assert eligible_queue.status == "completed"
        assert eligible_profile.full_text_status == "available"
        assert restricted_queue.status == "pending"
        assert captured_ingest_kwargs["source_url"] == "https://example.test/open.pdf"


def test_full_text_worker_defers_exhausted_source_without_retrying_same_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    for table in (
        Paper.__table__,
        PaperContentProfile.__table__,
        FullTextQueueItem.__table__,
        FullTextSourceAttempt.__table__,
    ):
        table.create(engine)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, content=b"missing", request=request)

    with Session(engine) as session:
        paper = Paper(
            title="Removed OA PDF",
            is_oa=True,
            pdf_url="https://example.test/missing.pdf",
            primary_source="openalex",
            source_record_id="W-MISSING",
            retrieved_at=datetime.now(timezone.utc),
            provenance={},
        )
        session.add(paper)
        session.flush()
        profile = PaperContentProfile(paper_id=paper.id, full_text_status="queued")
        queue = FullTextQueueItem(
            paper_id=paper.id,
            priority=90,
            status="pending",
            rights_status="open_access",
        )
        session.add_all([profile, queue])
        session.commit()

        result = FullTextEnrichmentWorker(
            session,
            Settings(database_url="sqlite+pysqlite:///:memory:"),
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        ).run(max_items=1)

        session.refresh(queue)
        session.refresh(profile)
        assert result["selected"] == 1
        assert result["completed"] == 0
        assert result["failed"] == 1
        assert result["deferred"] == 1
        assert queue.status == "pending"
        assert queue.attempts == 1
        assert queue.next_attempt_at is not None
        assert queue.failure_kind == "source_resolution_failure"
        assert queue.last_error is not None
        assert profile.full_text_status == "queued"
        attempt = session.query(FullTextSourceAttempt).one()
        assert attempt.failure_kind == "http_404"
        assert attempt.domain == "example.test"


def test_full_text_worker_does_not_mark_empty_extraction_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    for table in (
        Paper.__table__,
        PaperContentProfile.__table__,
        FullTextQueueItem.__table__,
        FullTextSourceAttempt.__table__,
    ):
        table.create(engine)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"%PDF-1.7\nempty", request=request)

    def fake_ingest(*_args: object, **_kwargs: object) -> object:
        return SimpleNamespace(chunk_count=0, extraction_status="text_extraction_failed_ocr_not_run")

    monkeypatch.setattr(PdfEvidenceService, "ingest", fake_ingest)
    with Session(engine) as session:
        paper = Paper(
            title="Image-only OA PDF",
            is_oa=True,
            pdf_url="https://example.test/image-only.pdf",
            primary_source="openalex",
            source_record_id="W-IMAGE",
            retrieved_at=datetime.now(timezone.utc),
            provenance={},
        )
        session.add(paper)
        session.flush()
        profile = PaperContentProfile(paper_id=paper.id, full_text_status="queued")
        queue = FullTextQueueItem(
            paper_id=paper.id,
            priority=90,
            status="pending",
            rights_status="open_access",
        )
        session.add_all([profile, queue])
        session.commit()

        result = FullTextEnrichmentWorker(
            session,
            Settings(database_url="sqlite+pysqlite:///:memory:"),
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        ).run(max_items=1)

        session.refresh(queue)
        session.refresh(profile)
        assert result["completed"] == 0
        assert result["failed"] == 1
        assert queue.status == "pending"
        assert queue.attempts == 1
        assert queue.next_attempt_at is not None
        assert profile.full_text_status == "queued"
        assert session.query(FullTextSourceAttempt).one().failure_kind == "extraction_failure"


def test_full_text_worker_switches_to_fresh_openalex_oa_location(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    for table in (
        Paper.__table__,
        PaperContentProfile.__table__,
        FullTextQueueItem.__table__,
        FullTextSourceAttempt.__table__,
    ):
        table.create(engine)

    old_url = "https://publisher.example/blocked.pdf"
    alt_url = "https://repository.example/open.pdf"

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).startswith("https://api.openalex.org/works/W-ALT"):
            return httpx.Response(
                200,
                json={
                    "best_oa_location": {
                        "is_oa": True,
                        "pdf_url": alt_url,
                        "license": "cc-by",
                    },
                    "primary_location": {
                        "is_oa": True,
                        "pdf_url": old_url,
                        "license": "cc-by",
                    },
                    "locations": [],
                },
                request=request,
            )
        if str(request.url) == old_url:
            return httpx.Response(403, content=b"blocked", request=request)
        if str(request.url) == alt_url:
            return httpx.Response(200, content=b"%PDF-1.7\nalt", request=request)
        raise AssertionError(f"Unexpected URL: {request.url}")

    monkeypatch.setattr(
        PdfEvidenceService,
        "ingest",
        lambda *_args, **_kwargs: SimpleNamespace(chunk_count=7, extraction_status="extracted"),
    )

    with Session(engine) as session:
        paper = Paper(
            title="OA paper with repository fallback",
            openalex_id="W-ALT",
            is_oa=True,
            pdf_url=old_url,
            publisher="Example Publisher",
            primary_source="openalex",
            source_record_id="W-ALT",
            retrieved_at=datetime.now(timezone.utc),
            provenance={},
        )
        session.add(paper)
        session.flush()
        profile = PaperContentProfile(paper_id=paper.id, full_text_status="queued")
        queue = FullTextQueueItem(
            paper_id=paper.id,
            priority=90,
            status="pending",
            rights_status="open_access",
        )
        session.add_all([profile, queue])
        session.commit()

        result = FullTextEnrichmentWorker(
            session,
            Settings(database_url="sqlite+pysqlite:///:memory:"),
            client=httpx.Client(transport=httpx.MockTransport(handler)),
            worker_id="test-worker",
        ).run(max_items=1)

        session.refresh(queue)
        session.refresh(paper)
        assert result["completed"] == 1
        assert queue.status == "completed"
        assert queue.worker_id is None
        assert queue.lease_expires_at is None
        assert paper.pdf_url == alt_url
        attempts = session.query(FullTextSourceAttempt).order_by(FullTextSourceAttempt.started_at).all()
        assert [(row.source_url, row.status, row.failure_kind) for row in attempts] == [
            (old_url, "failed", "http_403"),
            (alt_url, "completed", None),
        ]
        assert attempts[0].publisher == "Example Publisher"


def test_openalex_content_pdf_candidate_requires_key_and_keeps_key_out_of_url() -> None:
    work_id = "W-CONTENT"
    content_url = f"https://content.openalex.org/works/{work_id}.pdf"
    content_xml_url = f"https://content.openalex.org/works/{work_id}.grobid.xml"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params.get("api_key") == "test-openalex-key"
        assert request.url.params.get("select") == (
            "best_oa_location,primary_location,locations,has_content,content_urls"
        )
        return httpx.Response(
            200,
            json={
                "has_content": {"pdf": True, "grobid_xml": True},
                "content_urls": {"pdf": content_url, "grobid_xml": content_xml_url},
                "best_oa_location": None,
                "primary_location": None,
                "locations": [],
            },
            request=request,
        )

    paper = Paper(
        title="OpenAlex content-backed OA paper",
        openalex_id=work_id,
        is_oa=True,
        license="cc-by",
        primary_source="openalex",
        source_record_id=work_id,
        retrieved_at=datetime.now(timezone.utc),
        provenance={},
    )
    client = httpx.Client(transport=httpx.MockTransport(handler))
    resolver = OpenAccessSourceResolver(
        Settings(openalex_api_key="test-openalex-key"),
        client,
    )
    candidates = resolver.resolve(paper)

    assert len(candidates) == 2
    by_kind = {candidate.source_kind: candidate for candidate in candidates}
    pdf_candidate = by_kind["openalex_content_pdf"]
    xml_candidate = by_kind["openalex_content_grobid_xml"]
    assert pdf_candidate.url == content_url
    assert "api_key" not in pdf_candidate.url
    assert dict(pdf_candidate.request_params) == {"api_key": "test-openalex-key"}
    assert xml_candidate.media_type == "xml"
    assert xml_candidate.url == content_xml_url
    assert "api_key" not in xml_candidate.url
    assert dict(xml_candidate.request_params) == {"api_key": "test-openalex-key"}


def test_openalex_content_pdf_candidate_is_disabled_without_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params.get("api_key") is None
        return httpx.Response(
            200,
            json={
                "has_content": {"pdf": True, "grobid_xml": True},
                "content_urls": {
                    "pdf": "https://content.openalex.org/works/W-NO-KEY.pdf",
                    "grobid_xml": None,
                },
                "best_oa_location": None,
                "primary_location": None,
                "locations": [],
            },
            request=request,
        )

    paper = Paper(
        title="OpenAlex content paper without API key",
        openalex_id="W-NO-KEY",
        is_oa=True,
        primary_source="openalex",
        source_record_id="W-NO-KEY",
        retrieved_at=datetime.now(timezone.utc),
        provenance={},
    )
    candidates = OpenAccessSourceResolver(
        Settings(openalex_api_key=None),
        httpx.Client(transport=httpx.MockTransport(handler)),
    ).resolve(paper)

    assert candidates == []


def test_openalex_content_failure_does_not_persist_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    for table in (
        Paper.__table__,
        PaperContentProfile.__table__,
        FullTextQueueItem.__table__,
        FullTextSourceAttempt.__table__,
    ):
        table.create(engine)

    api_key = "super-secret-openalex-key"
    content_url = "https://content.openalex.org/works/W-SECRET.pdf"

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.startswith("https://api.openalex.org/works/W-SECRET"):
            return httpx.Response(
                200,
                json={
                    "has_content": {"pdf": True, "grobid_xml": False},
                    "content_urls": {"pdf": content_url, "grobid_xml": None},
                    "best_oa_location": None,
                    "primary_location": None,
                    "locations": [],
                },
                request=request,
            )
        if url.startswith(content_url):
            assert request.url.params.get("api_key") == api_key
            return httpx.Response(403, content=b"blocked", request=request)
        raise AssertionError(f"Unexpected URL: {url}")

    with Session(engine) as session:
        paper = Paper(
            title="OpenAlex content error redaction",
            openalex_id="W-SECRET",
            is_oa=True,
            primary_source="openalex",
            source_record_id="W-SECRET",
            retrieved_at=datetime.now(timezone.utc),
            provenance={},
        )
        session.add(paper)
        session.flush()
        queue = FullTextQueueItem(
            paper_id=paper.id,
            priority=90,
            status="pending",
            rights_status="open_access",
        )
        session.add_all(
            [
                queue,
                PaperContentProfile(paper_id=paper.id, full_text_status="queued"),
            ]
        )
        session.flush()
        session.commit()

        worker = FullTextEnrichmentWorker(
            session,
            Settings(openalex_api_key=api_key),
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        result = worker.run(max_items=1)
        session.refresh(queue)
        attempt = session.query(FullTextSourceAttempt).one()

        assert result["failed"] == 1
        assert api_key not in (attempt.error_message or "")
        assert api_key not in (queue.last_error or "")
        assert api_key not in attempt.source_url


def test_openalex_content_daily_limit_skips_archive_and_preserves_public_pdf_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    for table in (
        Paper.__table__,
        PaperContentProfile.__table__,
        FullTextQueueItem.__table__,
        FullTextSourceAttempt.__table__,
    ):
        table.create(engine)

    public_url = "https://repository.example/public.pdf"
    content_url = "https://content.openalex.org/works/W-BUDGET.pdf"

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.startswith("https://api.openalex.org/works/W-BUDGET"):
            return httpx.Response(
                200,
                json={
                    "has_content": {"pdf": True, "grobid_xml": False},
                    "content_urls": {"pdf": content_url, "grobid_xml": None},
                    "best_oa_location": {
                        "is_oa": True,
                        "pdf_url": public_url,
                        "license": "cc-by",
                    },
                    "primary_location": None,
                    "locations": [],
                },
                request=request,
            )
        if url == public_url:
            return httpx.Response(200, content=b"%PDF-1.7\npublic", request=request)
        if url.startswith(content_url):
            raise AssertionError("OpenAlex content archive should be disabled by daily limit")
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(
        PdfEvidenceService,
        "ingest",
        lambda *_args, **_kwargs: SimpleNamespace(chunk_count=4, extraction_status="extracted"),
    )

    with Session(engine) as session:
        paper = Paper(
            title="Archive budget fallback",
            openalex_id="W-BUDGET",
            is_oa=True,
            pdf_url="https://blocked.example/current.pdf",
            primary_source="openalex",
            source_record_id="W-BUDGET",
            retrieved_at=datetime.now(timezone.utc),
            provenance={},
        )
        session.add(paper)
        session.flush()
        queue = FullTextQueueItem(
            paper_id=paper.id,
            priority=90,
            status="pending",
            rights_status="open_access",
        )
        session.add_all(
            [
                queue,
                PaperContentProfile(paper_id=paper.id, full_text_status="queued"),
            ]
        )
        session.flush()
        now = datetime.now(timezone.utc)
        for index in range(3):
            session.add(
                FullTextSourceAttempt(
                    queue_item_id=queue.id,
                    paper_id=paper.id,
                    source_url=f"https://blocked.example/history-{index}.pdf",
                    domain="blocked.example",
                    publisher="Blocked Publisher",
                    source_kind="paper_pdf_url",
                    status="failed",
                    failure_kind="http_403",
                    http_status=403,
                    error_message="blocked",
                    started_at=now,
                    finished_at=now,
                )
            )
        session.commit()

        result = FullTextEnrichmentWorker(
            session,
            Settings(
                openalex_api_key="test-key",
                openalex_content_daily_limit=0,
            ),
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        ).run(max_items=1)

        session.refresh(paper)
        assert result["completed"] == 1
        assert paper.pdf_url == public_url
        assert session.query(FullTextSourceAttempt).filter_by(source_kind="openalex_content_pdf").count() == 0


def test_europe_pmc_resolver_returns_only_open_access_rest_full_text() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params.get("query") == "DOI:10.1000/example AND OPEN_ACCESS:Y"
        return httpx.Response(
            200,
            json={
                "resultList": {
                    "result": [
                        {
                            "pmcid": "PMC1234567",
                            "doi": "10.1000/example",
                            "isOpenAccess": "Y",
                            "license": "cc by",
                        }
                    ]
                }
            },
            request=request,
        )

    paper = Paper(
        title="Europe PMC candidate",
        doi="10.1000/example",
        is_oa=True,
        primary_source="openalex",
        source_record_id="W-EPMC",
        retrieved_at=datetime.now(timezone.utc),
        provenance={},
    )
    resolver = EuropePmcSourceResolver(httpx.Client(transport=httpx.MockTransport(handler)))
    candidates = resolver.resolve(paper)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.source_kind == "europe_pmc_oa_xml"
    assert candidate.media_type == "xml"
    assert candidate.source_record_id == "PMC1234567"
    assert candidate.license == "cc by"
    assert candidate.url.endswith("/PMC1234567/fullTextXML")


def test_xml_evidence_service_ingests_jats_full_text(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    for table in (
        Paper.__table__,
        IngestionRun.__table__,
        PaperVersion.__table__,
        PaperChunk.__table__,
    ):
        table.create(engine)

    class FakeEmbeddingProvider:
        name = "test_xml_provider"
        model = "test-xml-model-v1"

        def embed_document(self, _text: str) -> list[float]:
            return [0.0] * 384

    monkeypatch.setattr(
        "research_lab.xml_pipeline.build_embedding_provider",
        lambda _settings: FakeEmbeddingProvider(),
    )
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <article><body><sec><title>Methods</title>
    <p>We evaluate an AI-enabled workflow using longitudinal evidence.</p>
    <p>Results support careful implementation under real operating constraints.</p>
    </sec></body></article>"""

    with Session(engine) as session:
        paper = Paper(
            title="Europe PMC structured evidence",
            doi="10.1000/xml",
            is_oa=True,
            language="en",
            primary_source="openalex",
            source_record_id="W-XML",
            retrieved_at=datetime.now(timezone.utc),
            provenance={},
        )
        session.add(paper)
        session.commit()

        result = XmlEvidenceService(
            session,
            Settings(private_data_root=tmp_path / "private", private_data_require_external=False),
        ).ingest(
            paper.id,
            xml,
            source="europe_pmc_oa_xml",
            source_record_id="PMC7654321",
            source_url=(
                "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC7654321/fullTextXML"
            ),
            license_label="cc by",
        )

        version = session.get(PaperVersion, result.version_id)
        chunk = session.query(PaperChunk).filter_by(paper_id=paper.id).one()
        session.refresh(paper)
        assert result.extraction_status == "extracted"
        assert result.chunk_count == 1
        assert version is not None
        assert version.source == "europe_pmc_oa_xml"
        assert version.source_record_id == "PMC7654321"
        assert version.source_metadata["media_type"] == "application/xml"
        assert version.source_metadata["extraction"]["method"] == "jats_xml"
        assert "AI-enabled workflow" in chunk.text
        assert chunk.embedding_provider == "test_xml_provider"
        document = paper.provenance["open_access_documents"][0]
        assert document["source_record_id"] == "PMC7654321"
        assert document["license"] == "cc by"


def test_full_text_worker_uses_europe_pmc_xml_after_blocked_publisher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    for table in (
        Paper.__table__,
        PaperContentProfile.__table__,
        FullTextQueueItem.__table__,
        FullTextSourceAttempt.__table__,
    ):
        table.create(engine)

    publisher_url = "https://publisher.example/blocked.pdf"
    europe_pmc_url = (
        "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC2468101/fullTextXML"
    )
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == publisher_url:
            return httpx.Response(403, content=b"blocked", request=request)
        if url.startswith("https://api.openalex.org/works/W-EPMC-WORKER"):
            return httpx.Response(
                200,
                json={
                    "has_content": {"pdf": False, "grobid_xml": False},
                    "content_urls": {"pdf": None, "grobid_xml": None},
                    "best_oa_location": None,
                    "primary_location": None,
                    "locations": [],
                },
                request=request,
            )
        if url.startswith("https://www.ebi.ac.uk/europepmc/webservices/rest/search"):
            return httpx.Response(
                200,
                json={
                    "resultList": {
                        "result": [
                            {
                                "pmcid": "PMC2468101",
                                "isOpenAccess": "Y",
                                "license": "cc by",
                            }
                        ]
                    }
                },
                request=request,
            )
        if url == europe_pmc_url:
            return httpx.Response(
                200,
                content=(
                    b"<?xml version='1.0'?><pmc-articleset>"
                    b"<article><body><p>Evidence</p></body></article>"
                    b"</pmc-articleset>"
                ),
                request=request,
            )
        raise AssertionError(f"Unexpected URL: {url}")

    def fake_xml_ingest(*_args: object, **kwargs: object) -> object:
        captured.update(kwargs)
        return SimpleNamespace(chunk_count=6, extraction_status="extracted")

    monkeypatch.setattr(XmlEvidenceService, "ingest", fake_xml_ingest)

    with Session(engine) as session:
        paper = Paper(
            title="Europe PMC worker fallback",
            doi="10.1000/europe-pmc-worker",
            openalex_id="W-EPMC-WORKER",
            is_oa=True,
            pdf_url=publisher_url,
            primary_source="openalex",
            source_record_id="W-EPMC-WORKER",
            retrieved_at=datetime.now(timezone.utc),
            provenance={},
        )
        session.add(paper)
        session.flush()
        queue = FullTextQueueItem(
            paper_id=paper.id,
            priority=90,
            status="pending",
            rights_status="open_access",
        )
        session.add_all(
            [
                queue,
                PaperContentProfile(paper_id=paper.id, full_text_status="queued"),
            ]
        )
        session.commit()

        result = FullTextEnrichmentWorker(
            session,
            Settings(),
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        ).run(max_items=1)

        session.refresh(paper)
        assert result["completed"] == 1
        assert paper.pdf_url == publisher_url
        assert captured["source_record_id"] == "PMC2468101"
        attempts = session.query(FullTextSourceAttempt).order_by(FullTextSourceAttempt.started_at).all()
        assert [(row.source_kind, row.status) for row in attempts] == [
            ("paper_pdf_url", "failed"),
            ("europe_pmc_oa_xml", "completed"),
        ]


def test_full_text_worker_refreshes_known_low_yield_domain_before_direct_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    for table in (
        Paper.__table__,
        PaperContentProfile.__table__,
        FullTextQueueItem.__table__,
        FullTextSourceAttempt.__table__,
    ):
        table.create(engine)

    current_url = "https://blocked.example/current.pdf"
    alternate_url = "https://repository.example/open.pdf"
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        calls.append(url)
        if url.startswith("https://api.openalex.org/works/W-LOW-YIELD"):
            return httpx.Response(
                200,
                json={
                    "best_oa_location": {
                        "is_oa": True,
                        "pdf_url": alternate_url,
                        "license": "cc-by",
                    },
                    "primary_location": {
                        "is_oa": True,
                        "pdf_url": current_url,
                        "license": "cc-by",
                    },
                    "locations": [],
                },
                request=request,
            )
        if url == alternate_url:
            return httpx.Response(200, content=b"%PDF-1.7\nhealthy-source", request=request)
        if url == current_url:
            raise AssertionError("Known low-yield direct source should have been deprioritized")
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(
        PdfEvidenceService,
        "ingest",
        lambda *_args, **_kwargs: SimpleNamespace(chunk_count=5, extraction_status="extracted"),
    )

    with Session(engine) as session:
        historical = Paper(
            title="Historical blocked-domain paper",
            is_oa=True,
            primary_source="openalex",
            source_record_id="W-HISTORY",
            retrieved_at=datetime.now(timezone.utc),
            provenance={},
        )
        current = Paper(
            title="Current paper with healthier OA fallback",
            openalex_id="W-LOW-YIELD",
            is_oa=True,
            pdf_url=current_url,
            primary_source="openalex",
            source_record_id="W-LOW-YIELD",
            retrieved_at=datetime.now(timezone.utc),
            provenance={},
        )
        session.add_all([historical, current])
        session.flush()
        historical_queue = FullTextQueueItem(
            paper_id=historical.id,
            priority=10,
            status="completed",
            rights_status="open_access",
        )
        current_queue = FullTextQueueItem(
            paper_id=current.id,
            priority=90,
            status="pending",
            rights_status="open_access",
        )
        session.add_all(
            [
                historical_queue,
                current_queue,
                PaperContentProfile(paper_id=current.id, full_text_status="queued"),
            ]
        )
        session.flush()
        now = datetime.now(timezone.utc)
        for index in range(3):
            session.add(
                FullTextSourceAttempt(
                    queue_item_id=historical_queue.id,
                    paper_id=historical.id,
                    source_url=f"https://blocked.example/history-{index}.pdf",
                    domain="blocked.example",
                    publisher="Blocked Publisher",
                    source_kind="paper_pdf_url",
                    status="failed",
                    failure_kind="http_403",
                    http_status=403,
                    error_message="historical 403",
                    started_at=now,
                    finished_at=now,
                )
            )
        session.commit()

        result = FullTextEnrichmentWorker(
            session,
            Settings(database_url="sqlite+pysqlite:///:memory:"),
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        ).run(max_items=1)

        session.refresh(current)
        assert result["completed"] == 1
        assert current.pdf_url == alternate_url
        assert calls[0].startswith("https://api.openalex.org/works/W-LOW-YIELD")
        assert current_url not in calls


def test_source_exhausted_backoff_grows_when_openalex_locations_do_not_change() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    for table in (
        Paper.__table__,
        PaperContentProfile.__table__,
        FullTextQueueItem.__table__,
        FullTextSourceAttempt.__table__,
    ):
        table.create(engine)

    source_url = "https://blocked.example/no-fallback.pdf"
    source_requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal source_requests
        url = str(request.url)
        if url.startswith("https://api.openalex.org/works/W-UNCHANGED"):
            return httpx.Response(
                200,
                json={
                    "best_oa_location": {
                        "is_oa": True,
                        "pdf_url": source_url,
                        "license": "cc-by",
                    },
                    "primary_location": None,
                    "locations": [],
                },
                request=request,
            )
        if url == source_url:
            source_requests += 1
            return httpx.Response(403, content=b"blocked", request=request)
        raise AssertionError(f"Unexpected URL: {url}")

    with Session(engine) as session:
        paper = Paper(
            title="OA source whose locations remain unchanged",
            openalex_id="W-UNCHANGED",
            is_oa=True,
            pdf_url=source_url,
            primary_source="openalex",
            source_record_id="W-UNCHANGED",
            retrieved_at=datetime.now(timezone.utc),
            provenance={},
        )
        session.add(paper)
        session.flush()
        queue = FullTextQueueItem(
            paper_id=paper.id,
            priority=90,
            status="pending",
            rights_status="open_access",
        )
        session.add_all(
            [
                queue,
                PaperContentProfile(paper_id=paper.id, full_text_status="queued"),
            ]
        )
        session.commit()
        client = httpx.Client(transport=httpx.MockTransport(handler))

        first = FullTextEnrichmentWorker(session, Settings(), client=client).run(max_items=1)
        session.refresh(queue)
        first_now = (
            datetime.now(timezone.utc)
            if queue.next_attempt_at and queue.next_attempt_at.tzinfo
            else datetime.now(timezone.utc).replace(tzinfo=None)
        )
        first_delay = queue.next_attempt_at - first_now if queue.next_attempt_at else timedelta(0)
        assert first["deferred"] == 1
        assert queue.failure_kind == "source_exhausted"
        assert first_delay > timedelta(hours=23)

        queue.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        session.commit()
        second = FullTextEnrichmentWorker(session, Settings(), client=client).run(max_items=1)
        session.refresh(queue)
        second_now = (
            datetime.now(timezone.utc)
            if queue.next_attempt_at and queue.next_attempt_at.tzinfo
            else datetime.now(timezone.utc).replace(tzinfo=None)
        )
        second_delay = queue.next_attempt_at - second_now if queue.next_attempt_at else timedelta(0)
        assert second["deferred"] == 1
        assert second_delay > timedelta(days=2)
        assert source_requests == 1
        source_resolution = queue.reason_factors["source_resolution"]
        assert source_resolution["unchanged_count"] == 1


def test_full_text_worker_recovers_stale_processing_lease(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    for table in (
        Paper.__table__,
        PaperContentProfile.__table__,
        FullTextQueueItem.__table__,
        FullTextSourceAttempt.__table__,
    ):
        table.create(engine)

    monkeypatch.setattr(
        PdfEvidenceService,
        "ingest",
        lambda *_args, **_kwargs: SimpleNamespace(chunk_count=2, extraction_status="extracted"),
    )
    with Session(engine) as session:
        paper = Paper(
            title="Stale leased paper",
            is_oa=True,
            pdf_url="https://example.test/stale.pdf",
            primary_source="openalex",
            source_record_id="W-STALE",
            retrieved_at=datetime.now(timezone.utc),
            provenance={},
        )
        session.add(paper)
        session.flush()
        session.add(PaperContentProfile(paper_id=paper.id, full_text_status="queued"))
        queue = FullTextQueueItem(
            paper_id=paper.id,
            priority=90,
            status="processing",
            rights_status="open_access",
            worker_id="dead-worker",
            claimed_at=datetime.now(timezone.utc) - timedelta(hours=1),
            lease_expires_at=datetime.now(timezone.utc) - timedelta(minutes=30),
        )
        session.add(queue)
        session.commit()

        client = httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, content=b"%PDF-1.7\nstale", request=request)
            )
        )
        result = FullTextEnrichmentWorker(session, Settings(), client=client).run(max_items=1)
        session.refresh(queue)
        assert result["stale_leases_recovered"] == 1
        assert result["completed"] == 1
        assert queue.status == "completed"
        assert queue.attempts == 1


def test_full_text_worker_requeues_only_legacy_failed_rows_without_attempt_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    for table in (
        Paper.__table__,
        PaperContentProfile.__table__,
        FullTextQueueItem.__table__,
        FullTextSourceAttempt.__table__,
    ):
        table.create(engine)

    monkeypatch.setattr(
        PdfEvidenceService,
        "ingest",
        lambda *_args, **_kwargs: SimpleNamespace(chunk_count=3, extraction_status="extracted"),
    )
    with Session(engine) as session:
        paper = Paper(
            title="Legacy failed OA row",
            is_oa=True,
            pdf_url="https://example.test/legacy.pdf",
            primary_source="openalex",
            source_record_id="W-LEGACY-FAILED",
            retrieved_at=datetime.now(timezone.utc),
            provenance={},
        )
        session.add(paper)
        session.flush()
        session.add(PaperContentProfile(paper_id=paper.id, full_text_status="failed"))
        queue = FullTextQueueItem(
            paper_id=paper.id,
            priority=90,
            status="failed",
            rights_status="open_access",
            attempts=1,
            last_error="HTTPStatusError: old worker failure",
        )
        session.add(queue)
        session.commit()

        client = httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, content=b"%PDF-1.7\nlegacy", request=request)
            )
        )
        result = FullTextEnrichmentWorker(session, Settings(), client=client).run(max_items=1)
        session.refresh(queue)
        assert result["legacy_failures_requeued"] == 1
        assert result["completed"] == 1
        assert queue.status == "completed"
        assert queue.attempts == 2


def test_pdf_evidence_service_preserves_open_access_provenance(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    for table in (
        Paper.__table__,
        IngestionRun.__table__,
        PaperVersion.__table__,
        PaperChunk.__table__,
    ):
        table.create(engine)

    class FakePage:
        def extract_text(self) -> str:
            return "Methods\nWe evaluate an AI-enabled workflow with a longitudinal field design."

    class FakeReader:
        def __init__(self, _stream: object) -> None:
            self.pages = [FakePage()]

    class FakeEmbeddingProvider:
        name = "test_full_text_provider"
        model = "test-full-text-model-v1"

        def embed_document(self, _text: str) -> list[float]:
            return [0.0] * 384

    monkeypatch.setattr("research_lab.pdf_pipeline.PdfReader", FakeReader)
    monkeypatch.setattr(
        "research_lab.pdf_pipeline.build_embedding_provider",
        lambda _settings: FakeEmbeddingProvider(),
    )

    with Session(engine) as session:
        paper = Paper(
            title="Rights-safe OA evidence",
            is_oa=True,
            pdf_url="https://example.test/rights-safe.pdf",
            license="cc-by",
            primary_source="openalex",
            source_record_id="W-PROVENANCE",
            retrieved_at=datetime.now(timezone.utc),
            provenance={},
        )
        session.add(paper)
        session.commit()

        settings = Settings(
            database_url="sqlite+pysqlite:///:memory:",
            private_data_root=tmp_path / "private",
            private_data_require_external=False,
        )
        result = PdfEvidenceService(session, settings).ingest(
            paper.id,
            "rights-safe.pdf",
            b"%PDF-1.7\nprovenance-test",
            source="openalex_oa_pdf",
            source_url=paper.pdf_url,
            license_label="cc-by",
            redistributable=False,
        )

        version = session.get(PaperVersion, result.version_id)
        chunk = session.query(PaperChunk).filter(PaperChunk.paper_id == paper.id).one()
        session.refresh(paper)

        assert result.extraction_status == "extracted"
        assert result.chunk_count == 1
        assert version is not None
        assert version.license == "cc-by"
        assert version.payload_hash
        assert version.source_metadata["source_url"] == paper.pdf_url
        assert version.source_metadata["redistributable"] is False
        assert version.source_metadata["extraction"] == {
            "method": "pypdf",
            "ocr_run": False,
            "status": "extracted",
            "page_count": 1,
            "chunk_count": 1,
            "extracted_characters": 76,
            "nul_characters_removed": 0,
        }
        assert chunk.embedding_provider == "test_full_text_provider"
        assert chunk.embedding_model == "test-full-text-model-v1"
        oa_pdf = paper.provenance["open_access_pdfs"][0]
        assert oa_pdf["source_url"] == paper.pdf_url
        assert oa_pdf["license"] == "cc-by"
        assert oa_pdf["sha256"] == version.payload_hash
        assert oa_pdf["redistributable"] is False
        assert oa_pdf["extraction"]["ocr_run"] is False


def test_pdf_evidence_service_removes_postgres_nul_characters(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    for table in (
        Paper.__table__,
        IngestionRun.__table__,
        PaperVersion.__table__,
        PaperChunk.__table__,
    ):
        table.create(engine)

    class FakePage:
        def extract_text(self) -> str:
            return "Results\nAI\x00-enabled workflow evidence remains readable."

    class FakeReader:
        def __init__(self, _stream: object) -> None:
            self.pages = [FakePage()]

    class FakeEmbeddingProvider:
        name = "test"
        model = "test-v1"

        def embed_document(self, _text: str) -> list[float]:
            return [0.0] * 384

    monkeypatch.setattr("research_lab.pdf_pipeline.PdfReader", FakeReader)
    monkeypatch.setattr(
        "research_lab.pdf_pipeline.build_embedding_provider",
        lambda _settings: FakeEmbeddingProvider(),
    )

    with Session(engine) as session:
        paper = Paper(
            title="PDF containing a NUL character",
            is_oa=True,
            primary_source="openalex",
            source_record_id="W-NUL",
            retrieved_at=datetime.now(timezone.utc),
            provenance={},
        )
        session.add(paper)
        session.commit()
        result = PdfEvidenceService(
            session,
            Settings(private_data_root=tmp_path / "private", private_data_require_external=False),
        ).ingest(
            paper.id,
            "nul.pdf",
            b"%PDF-1.7\nnul-test",
            source="openalex_oa_pdf",
        )

        chunk = session.query(PaperChunk).filter_by(paper_id=paper.id).one()
        version = session.get(PaperVersion, result.version_id)
        assert "\x00" not in chunk.text
        assert version is not None
        assert version.source_metadata["extraction"]["nul_characters_removed"] == 1


def test_full_text_worker_rolls_back_failed_ingest_before_recording_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    for table in (
        Paper.__table__,
        PaperContentProfile.__table__,
        FullTextQueueItem.__table__,
        FullTextSourceAttempt.__table__,
    ):
        table.create(engine)

    def failed_flush(service: PdfEvidenceService, *_args: object, **_kwargs: object) -> object:
        service.session.add(
            Paper(
                title=None,  # type: ignore[arg-type]
                is_oa=False,
                primary_source="test",
                source_record_id="INVALID",
                retrieved_at=datetime.now(timezone.utc),
                provenance={},
            )
        )
        service.session.flush()
        raise AssertionError("flush should fail before this line")

    monkeypatch.setattr(PdfEvidenceService, "ingest", failed_flush)
    with Session(engine) as session:
        paper = Paper(
            title="Worker rollback regression",
            is_oa=True,
            pdf_url="https://example.test/rollback.pdf",
            primary_source="local",
            source_record_id="ROLLBACK",
            retrieved_at=datetime.now(timezone.utc),
            provenance={},
        )
        session.add(paper)
        session.flush()
        queue = FullTextQueueItem(
            paper_id=paper.id,
            priority=90,
            status="pending",
            rights_status="open_access",
        )
        session.add_all(
            [
                queue,
                PaperContentProfile(paper_id=paper.id, full_text_status="queued"),
            ]
        )
        session.commit()

        client = httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, content=b"%PDF-1.7\nrollback", request=request)
            )
        )
        result = FullTextEnrichmentWorker(session, Settings(), client=client).run(max_items=1)

        assert result["failed"] == 1
        attempt = session.query(FullTextSourceAttempt).one()
        assert attempt.failure_kind == "extraction_failure"
        assert queue.status == "failed"


def test_legacy_provenance_backfill_keeps_unknown_source_url_null(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    for table in (Paper.__table__, PaperVersion.__table__, PaperChunk.__table__):
        table.create(engine)

    class FakePage:
        def extract_text(self) -> str:
            return "Legacy full text reconstructed from the stored immutable PDF blob."

    class FakeReader:
        def __init__(self, _stream: object) -> None:
            self.pages = [FakePage()]

    monkeypatch.setattr("research_lab.full_text_provenance.PdfReader", FakeReader)

    data = b"%PDF-1.7\nlegacy"
    import hashlib

    digest = hashlib.sha256(data).hexdigest()
    with Session(engine) as session:
        paper = Paper(
            title="Legacy OA paper",
            is_oa=True,
            pdf_url="https://current.example/not-historical.pdf",
            primary_source="openalex",
            source_record_id="W-LEGACY",
            retrieved_at=datetime.now(timezone.utc),
            provenance={},
        )
        session.add(paper)
        session.flush()
        version = PaperVersion(
            paper_id=paper.id,
            source="openalex_oa_pdf",
            source_record_id=digest,
            version_label="private-full-text",
            retrieved_at=datetime.now(timezone.utc) - timedelta(days=2),
            license="cc-by",
            payload_hash=digest,
            source_metadata={"private_blob_id": f"{paper.id}/{digest}.pdf"},
        )
        session.add(version)
        session.commit()
        blob = tmp_path / "private" / str(paper.id) / f"{digest}.pdf"
        blob.parent.mkdir(parents=True)
        blob.write_bytes(data)

        result = backfill_full_text_provenance(
            session,
            Settings(private_data_root=tmp_path / "private", private_data_require_external=False),
        )
        session.refresh(version)
        session.refresh(paper)
        assert result["updated"] == 1
        assert version.source_metadata["source_url"] is None
        assert version.source_metadata["extraction"]["reconstructed_from_stored_blob"] is True
        assert version.source_metadata["provenance_backfill"]["source_url_reconstructed"] is False
        assert paper.provenance["open_access_pdfs"][0]["source_url"] is None

        second = backfill_full_text_provenance(
            session,
            Settings(private_data_root=tmp_path / "private", private_data_require_external=False),
        )
        assert second["updated"] == 0
        assert second["skipped_complete"] == 1


def test_arxiv_resolver_uses_known_repository_identifier() -> None:
    paper = Paper(
        title="Known arXiv paper",
        arxiv_id="2401.12345",
        primary_source="openalex",
        source_record_id="W-ARXIV",
        retrieved_at=datetime.now(timezone.utc),
        provenance={},
    )

    candidates = ArxivResolver().resolve(paper)

    assert len(candidates) == 1
    assert candidates[0].url == "https://arxiv.org/pdf/2401.12345"
    assert candidates[0].source_kind == "arxiv_pdf"


def test_arxiv_resolver_extracts_repository_identifier_from_doi() -> None:
    paper = Paper(
        title="Known arXiv DOI paper",
        doi="10.48550/arXiv.2401.12345",
        primary_source="openalex",
        source_record_id="W-ARXIV-DOI",
        retrieved_at=datetime.now(timezone.utc),
        provenance={},
    )

    candidates = ArxivResolver().resolve(paper)

    assert len(candidates) == 1
    assert candidates[0].url == "https://arxiv.org/pdf/2401.12345"
    assert candidates[0].source_record_id == "2401.12345"


def test_unpaywall_resolver_returns_verified_oa_pdf_locations() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["email"] == "researcher@example.test"
        return httpx.Response(
            200,
            json={
                "is_oa": True,
                "best_oa_location": {
                    "url_for_pdf": "https://repository.example/best.pdf",
                    "license": "cc-by",
                },
                "oa_locations": [
                    {
                        "url_for_pdf": "https://repository.example/best.pdf",
                        "license": "cc-by",
                    },
                    {
                        "url_for_pdf": "https://publisher.example/alternate.pdf",
                        "license": "cc-by-nc",
                    },
                ],
            },
            request=request,
        )

    paper = Paper(
        title="DOI paper",
        doi="10.1000/unpaywall",
        primary_source="openalex",
        source_record_id="W-UNPAYWALL",
        retrieved_at=datetime.now(timezone.utc),
        provenance={},
    )
    client = httpx.Client(transport=httpx.MockTransport(handler))

    candidates = UnpaywallSourceResolver(
        Settings(unpaywall_email="researcher@example.test"), client
    ).resolve(paper)

    assert [candidate.source_kind for candidate in candidates] == [
        "unpaywall_best_oa_pdf",
        "unpaywall_oa_pdf",
    ]
    assert [candidate.url for candidate in candidates] == [
        "https://repository.example/best.pdf",
        "https://publisher.example/alternate.pdf",
    ]


def test_core_resolver_uses_bearer_auth_and_official_download_fallback() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer core-secret"
        assert request.url.params["q"] == 'doi:"10.1000/core"'
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": 12345,
                        "doi": "https://doi.org/10.1000/CORE",
                        "downloadUrl": "",
                        "sourceFulltextUrls": [],
                        "fulltextStatus": "enabled",
                        "fullText": "Extracted full text",
                        "license": "cc-by",
                    }
                ]
            },
            request=request,
        )

    paper = Paper(
        title="CORE paper",
        doi="10.1000/core",
        primary_source="openalex",
        source_record_id="W-CORE",
        retrieved_at=datetime.now(timezone.utc),
        provenance={},
    )
    client = httpx.Client(transport=httpx.MockTransport(handler))

    candidates = CoreSourceResolver(Settings(core_api_key="core-secret"), client).resolve(paper)

    assert len(candidates) == 1
    assert candidates[0].url == "https://api.core.ac.uk/v3/outputs/12345/download"
    assert candidates[0].source_kind == "core_api_download_pdf"
    assert dict(candidates[0].request_headers) == {"Authorization": "Bearer core-secret"}
    assert "core-secret" not in repr(candidates[0])


def test_preprint_resolver_uses_latest_biorxiv_jats_and_pdf() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "collection": [
                    {
                        "doi": "10.1101/339747",
                        "version": "1",
                        "server": "bioRxiv",
                        "license": "cc-by-nc-nd",
                        "jatsxml": "https://www.biorxiv.org/content/early/2018/06/05/339747.source.xml",
                    },
                    {
                        "doi": "10.1101/339747",
                        "version": "4",
                        "server": "bioRxiv",
                        "license": "cc-by",
                        "jatsxml": "https://www.biorxiv.org/content/early/2019/05/10/339747.source.xml",
                    },
                ]
            },
            request=request,
        )

    paper = Paper(
        title="bioRxiv paper",
        doi="10.1101/339747",
        primary_source="openalex",
        source_record_id="W-BIORXIV",
        retrieved_at=datetime.now(timezone.utc),
        provenance={},
    )
    client = httpx.Client(transport=httpx.MockTransport(handler))

    candidates = PreprintSourceResolver(Settings(), client).resolve(paper)

    assert [candidate.source_kind for candidate in candidates] == [
        "biorxiv_jats_xml",
        "biorxiv_pdf",
    ]
    assert candidates[0].url.endswith("/2019/05/10/339747.source.xml")
    assert candidates[1].url.endswith("/2019/05/10/339747.full.pdf")


def test_preprint_resolver_uses_cambridge_open_engage_chemrxiv_asset() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "/items/doi/10.26434/chemrxiv-2024-abcd-v2" in str(request.url)
        return httpx.Response(
            200,
            json={
                "id": "item-123",
                "doi": "10.26434/chemrxiv-2024-abcd-v2",
                "license": {"name": "CC BY 4.0"},
                "asset": {
                    "mimeType": "application/pdf",
                    "original": {"url": "https://www.cambridge.org/engage/assets/paper.pdf"},
                },
            },
            request=request,
        )

    paper = Paper(
        title="ChemRxiv paper",
        doi="10.26434/chemrxiv-2024-abcd-v2",
        primary_source="openalex",
        source_record_id="W-CHEMRXIV",
        retrieved_at=datetime.now(timezone.utc),
        provenance={},
    )
    client = httpx.Client(transport=httpx.MockTransport(handler))

    candidates = PreprintSourceResolver(Settings(), client).resolve(paper)

    assert len(candidates) == 1
    assert candidates[0].source_kind == "chemrxiv_pdf"
    assert candidates[0].license == "CC BY 4.0"
    assert candidates[0].source_record_id == "item-123"


def test_worker_discovers_unknown_oa_and_preserves_resolver_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    for table in (
        Paper.__table__,
        PaperContentProfile.__table__,
        FullTextQueueItem.__table__,
        FullTextSourceAttempt.__table__,
    ):
        table.create(engine)

    captured: dict[str, object] = {}

    def fake_ingest(*_args: object, **kwargs: object) -> object:
        captured.update(kwargs)
        return SimpleNamespace(chunk_count=3, extraction_status="extracted")

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "europepmc" in url:
            return httpx.Response(200, json={"resultList": {"result": []}}, request=request)
        if "unpaywall" in url:
            return httpx.Response(
                200,
                json={
                    "is_oa": True,
                    "best_oa_location": {
                        "url_for_pdf": "https://repository.example/discovered.pdf",
                        "license": "cc-by",
                    },
                    "oa_locations": [],
                },
                request=request,
            )
        if url == "https://repository.example/discovered.pdf":
            return httpx.Response(200, content=b"%PDF-1.7\ndiscovered", request=request)
        raise AssertionError(f"Unexpected request: {url}")

    monkeypatch.setattr(PdfEvidenceService, "ingest", fake_ingest)
    with Session(engine) as session:
        paper = Paper(
            title="Previously unknown OA paper",
            doi="10.1000/discovered",
            is_oa=False,
            primary_source="crossref",
            source_record_id="10.1000/discovered",
            retrieved_at=datetime.now(timezone.utc),
            provenance={},
        )
        session.add(paper)
        session.flush()
        profile = PaperContentProfile(
            paper_id=paper.id,
            full_text_status="queued",
            full_text_access="unknown",
            rights_status="unknown",
        )
        queue = FullTextQueueItem(
            paper_id=paper.id,
            priority=30,
            status="pending",
            rights_status="unknown",
        )
        session.add_all([profile, queue])
        session.commit()

        result = FullTextEnrichmentWorker(
            session,
            Settings(unpaywall_email="researcher@example.test"),
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        ).run(max_items=1)

        session.refresh(paper)
        session.refresh(profile)
        session.refresh(queue)
        assert result["completed"] == 1
        assert paper.is_oa is True
        assert queue.rights_status == "open_access"
        assert profile.full_text_access == "open_access"
        assert captured["source"] == "unpaywall_best_oa_pdf"
        assert session.query(FullTextSourceAttempt).one().source_kind == "unpaywall_best_oa_pdf"


# =============================================================================
# Adapter tests for Sci-Hub and LibGen result conversion
# =============================================================================


def test_convert_scihub_result_to_candidate_with_valid_pdf_url() -> None:
    """Test SciHubResult → OpenAccessPdfCandidate conversion with valid PDF URL."""
    from research_lab.full_text_sources import convert_resolver_result_to_candidate

    # Mock SciHubResult
    class MockSciHubResult:
        pdf_url = "https://sci-hub.se/download/10.1038/s41586-020-2649-2"
        source_kind = "sci_hub_pdf"
        retrieved_at = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
        doi = "10.1038/s41586-020-2649-2"
        domain_used = "sci-hub.se"
        error = None

    result = MockSciHubResult()
    candidate = convert_resolver_result_to_candidate(result)

    assert candidate is not None
    assert candidate.pdf_url == "https://sci-hub.se/download/10.1038/s41586-020-2649-2"
    assert candidate.source_kind == "sci_hub_pdf"
    assert candidate.metadata["doi"] == "10.1038/s41586-020-2649-2"
    assert candidate.metadata["domain_used"] == "sci-hub.se"


def test_convert_scihub_result_to_candidate_without_pdf_url() -> None:
    """Test SciHubResult → OpenAccessPdfCandidate conversion without PDF URL returns None."""
    from research_lab.full_text_sources import convert_resolver_result_to_candidate

    # Mock SciHubResult without PDF
    class MockSciHubResultNoPdf:
        pdf_url = None
        source_kind = "sci_hub_error"
        retrieved_at = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
        doi = "10.1038/s41586-020-2649-2"
        domain_used = "sci-hub.se"
        error = "PDF not found"

    result = MockSciHubResultNoPdf()
    candidate = convert_resolver_result_to_candidate(result)

    assert candidate is None


def test_convert_libgen_result_to_candidate_with_valid_pdf_url() -> None:
    """Test LibGenResult → OpenAccessPdfCandidate conversion with valid PDF URL."""
    from research_lab.full_text_sources import convert_resolver_result_to_candidate

    # Mock LibGenResult
    class MockLibGenResult:
        pdf_url = "https://libgen.rs/download/book/123456"
        source_kind = "libgen_pdf"
        retrieved_at = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
        identifier = "123456"
        doi = None
        isbn = "978-0-123456-78-9"
        error = None

    result = MockLibGenResult()
    candidate = convert_resolver_result_to_candidate(result)

    assert candidate is not None
    assert candidate.pdf_url == "https://libgen.rs/download/book/123456"
    assert candidate.source_kind == "libgen_pdf"
    assert candidate.metadata["identifier"] == "123456"
    assert candidate.metadata["isbn"] == "978-0-123456-78-9"


def test_convert_libgen_result_to_candidate_without_pdf_url() -> None:
    """Test LibGenResult → OpenAccessPdfCandidate conversion without PDF URL returns None."""
    from research_lab.full_text_sources import convert_resolver_result_to_candidate

    # Mock LibGenResult without PDF
    class MockLibGenResultNoPdf:
        pdf_url = None
        source_kind = "libgen_error"
        retrieved_at = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
        identifier = "123456"
        doi = None
        isbn = "978-0-123456-78-9"
        error = "File not found"

    result = MockLibGenResultNoPdf()
    candidate = convert_resolver_result_to_candidate(result)

    assert candidate is None


def test_convert_resolver_result_to_candidate_with_unsupported_type() -> None:
    """Test convert_resolver_result_to_candidate with unsupported type returns None."""
    from research_lab.full_text_sources import convert_resolver_result_to_candidate

    # Unsupported object
    result = {"pdf_url": "https://example.com/test.pdf"}
    candidate = convert_resolver_result_to_candidate(result)

    assert candidate is None
