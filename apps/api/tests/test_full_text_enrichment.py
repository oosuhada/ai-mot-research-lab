from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from research_lab.config import Settings
from research_lab.full_text_enrichment import FullTextEnrichmentWorker
from research_lab.full_text_provenance import backfill_full_text_provenance
from research_lab.full_text_sources import OpenAccessSourceResolver
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
            retrieved_at=datetime.now(UTC),
            provenance={},
        )
        restricted = Paper(
            title="Restricted paper",
            is_oa=False,
            primary_source="openalex",
            source_record_id="W-CLOSED",
            retrieved_at=datetime.now(UTC),
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
            retrieved_at=datetime.now(UTC),
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
            retrieved_at=datetime.now(UTC),
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
            retrieved_at=datetime.now(UTC),
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

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params.get("api_key") == "test-openalex-key"
        assert request.url.params.get("select") == (
            "best_oa_location,primary_location,locations,has_content,content_urls"
        )
        return httpx.Response(
            200,
            json={
                "has_content": {"pdf": True, "grobid_xml": True},
                "content_urls": {"pdf": content_url, "grobid_xml": None},
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
        retrieved_at=datetime.now(UTC),
        provenance={},
    )
    client = httpx.Client(transport=httpx.MockTransport(handler))
    resolver = OpenAccessSourceResolver(
        Settings(openalex_api_key="test-openalex-key"),
        client,
    )
    candidates = resolver.resolve(paper)

    assert len(candidates) == 1
    assert candidates[0].source_kind == "openalex_content_pdf"
    assert candidates[0].url == content_url
    assert "api_key" not in candidates[0].url
    assert dict(candidates[0].request_params) == {"api_key": "test-openalex-key"}


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
        retrieved_at=datetime.now(UTC),
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
            retrieved_at=datetime.now(UTC),
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
            retrieved_at=datetime.now(UTC),
            provenance={},
        )
        current = Paper(
            title="Current paper with healthier OA fallback",
            openalex_id="W-LOW-YIELD",
            is_oa=True,
            pdf_url=current_url,
            primary_source="openalex",
            source_record_id="W-LOW-YIELD",
            retrieved_at=datetime.now(UTC),
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
        now = datetime.now(UTC)
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
            retrieved_at=datetime.now(UTC),
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
            datetime.now(UTC)
            if queue.next_attempt_at and queue.next_attempt_at.tzinfo
            else datetime.now(UTC).replace(tzinfo=None)
        )
        first_delay = queue.next_attempt_at - first_now if queue.next_attempt_at else timedelta(0)
        assert first["deferred"] == 1
        assert queue.failure_kind == "source_exhausted"
        assert first_delay > timedelta(hours=23)

        queue.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
        second = FullTextEnrichmentWorker(session, Settings(), client=client).run(max_items=1)
        session.refresh(queue)
        second_now = (
            datetime.now(UTC)
            if queue.next_attempt_at and queue.next_attempt_at.tzinfo
            else datetime.now(UTC).replace(tzinfo=None)
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
            retrieved_at=datetime.now(UTC),
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
            claimed_at=datetime.now(UTC) - timedelta(hours=1),
            lease_expires_at=datetime.now(UTC) - timedelta(minutes=30),
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
            retrieved_at=datetime.now(UTC),
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
            retrieved_at=datetime.now(UTC),
            provenance={},
        )
        session.add(paper)
        session.commit()

        settings = Settings(
            database_url="sqlite+pysqlite:///:memory:",
            private_data_root=tmp_path / "private",
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
            retrieved_at=datetime.now(UTC),
            provenance={},
        )
        session.add(paper)
        session.commit()
        result = PdfEvidenceService(
            session,
            Settings(private_data_root=tmp_path / "private"),
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
                retrieved_at=datetime.now(UTC),
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
            retrieved_at=datetime.now(UTC),
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
            retrieved_at=datetime.now(UTC),
            provenance={},
        )
        session.add(paper)
        session.flush()
        version = PaperVersion(
            paper_id=paper.id,
            source="openalex_oa_pdf",
            source_record_id=digest,
            version_label="private-full-text",
            retrieved_at=datetime.now(UTC) - timedelta(days=2),
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
            Settings(private_data_root=tmp_path / "private"),
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
            Settings(private_data_root=tmp_path / "private"),
        )
        assert second["updated"] == 0
        assert second["skipped_complete"] == 1
