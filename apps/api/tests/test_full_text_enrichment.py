from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from research_lab.config import Settings
from research_lab.full_text_enrichment import FullTextEnrichmentWorker
from research_lab.models import (
    FullTextQueueItem,
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
    for table in (Paper.__table__, PaperContentProfile.__table__, FullTextQueueItem.__table__):
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
        assert result == {
            "selected": 1,
            "completed": 1,
            "failed": 0,
            "restricted_or_missing": 0,
        }
        assert eligible_queue.status == "completed"
        assert eligible_profile.full_text_status == "available"
        assert restricted_queue.status == "pending"
        assert captured_ingest_kwargs["source_url"] == "https://example.test/open.pdf"


def test_full_text_worker_marks_permanent_http_failure_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    for table in (Paper.__table__, PaperContentProfile.__table__, FullTextQueueItem.__table__):
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
        assert result == {
            "selected": 1,
            "completed": 0,
            "failed": 1,
            "restricted_or_missing": 0,
        }
        assert queue.status == "failed"
        assert queue.attempts == 1
        assert queue.next_attempt_at is None
        assert queue.last_error is not None
        assert queue.last_error.startswith("HTTPStatusError:")
        assert profile.full_text_status == "failed"


def test_full_text_worker_does_not_mark_empty_extraction_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    for table in (Paper.__table__, PaperContentProfile.__table__, FullTextQueueItem.__table__):
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
        }
        assert chunk.embedding_provider == "test_full_text_provider"
        assert chunk.embedding_model == "test-full-text-model-v1"
        oa_pdf = paper.provenance["open_access_pdfs"][0]
        assert oa_pdf["source_url"] == paper.pdf_url
        assert oa_pdf["license"] == "cc-by"
        assert oa_pdf["sha256"] == version.payload_hash
        assert oa_pdf["redistributable"] is False
        assert oa_pdf["extraction"]["ocr_run"] is False
