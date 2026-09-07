from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from research_lab.config import Settings
from research_lab.full_text_sources import OpenAccessPdfCandidate
from research_lab.models import FullTextQueueItem, FullTextSourceAttempt, Paper, PaperContentProfile
from research_lab.paper_search_mcp_worker import PaperSearchMcpFullTextWorker
from research_lab.pdf_pipeline import PdfEvidenceService


def _tables(engine: object) -> None:
    for table in (
        Paper.__table__,
        PaperContentProfile.__table__,
        FullTextQueueItem.__table__,
        FullTextSourceAttempt.__table__,
    ):
        table.create(engine)  # type: ignore[arg-type]


def test_paper_search_mcp_worker_can_use_deferred_item_without_breaking_regular_cooldown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    _tables(engine)
    future = datetime.now(timezone.utc) + timedelta(days=3)
    monkeypatch.setattr(
        PdfEvidenceService,
        "ingest",
        lambda *_args, **_kwargs: SimpleNamespace(chunk_count=5, extraction_status="extracted"),
    )
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=b"%PDF-1.7\nmcp", request=request)
        )
    )
    with Session(engine) as session:
        paper = Paper(
            title="Repository fallback paper",
            doi="10.1000/mcp-worker",
            is_oa=True,
            primary_source="openalex",
            source_record_id="W-MCP-WORKER",
            retrieved_at=datetime.now(timezone.utc),
            provenance={},
        )
        session.add(paper)
        session.flush()
        session.add(PaperContentProfile(paper_id=paper.id, full_text_status="queued"))
        queue = FullTextQueueItem(
            paper_id=paper.id,
            status="pending",
            priority=90,
            rights_status="open_access",
            attempts=2,
            next_attempt_at=future,
            failure_kind="source_exhausted",
            last_error="regular cooldown",
        )
        session.add(queue)
        session.commit()

        worker = PaperSearchMcpFullTextWorker(
            session,
            Settings(paper_search_mcp_executable="/tmp/paper-search"),
            client=client,
        )
        worker.mcp_resolver.resolve = lambda _paper: [  # type: ignore[method-assign]
            OpenAccessPdfCandidate(
                url="https://repository.example/paper.pdf",
                license="cc-by",
                source_kind="paper_search_mcp_zenodo_pdf",
            )
        ]
        result = worker.run(max_items=1, min_prior_attempts=1)

        session.refresh(queue)
        assert result["completed"] == 1
        assert queue.status == "completed"
        assert queue.attempts == 2
        assert queue.next_attempt_at is None
        assert "paper_search_mcp_claim" not in queue.reason_factors


def test_paper_search_mcp_no_match_restores_regular_queue_state() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    _tables(engine)
    future = datetime.now(timezone.utc) + timedelta(days=3)
    with Session(engine) as session:
        paper = Paper(
            title="No repository copy",
            doi="10.1000/no-mcp-copy",
            is_oa=True,
            primary_source="openalex",
            source_record_id="W-NO-MCP",
            retrieved_at=datetime.now(timezone.utc),
            provenance={},
        )
        session.add(paper)
        session.flush()
        session.add(PaperContentProfile(paper_id=paper.id, full_text_status="queued"))
        queue = FullTextQueueItem(
            paper_id=paper.id,
            status="pending",
            priority=90,
            rights_status="open_access",
            attempts=3,
            next_attempt_at=future,
            failure_kind="source_exhausted",
            last_error="keep me",
        )
        session.add(queue)
        session.commit()

        worker = PaperSearchMcpFullTextWorker(
            session,
            Settings(paper_search_mcp_executable="/tmp/paper-search"),
            client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(404, request=request))),
        )
        worker.mcp_resolver.resolve = lambda _paper: []  # type: ignore[method-assign]
        result = worker.run(max_items=1, min_prior_attempts=1)

        session.refresh(queue)
        assert result["no_match"] == 1
        assert queue.status == "pending"
        assert queue.attempts == 3
        assert queue.failure_kind == "source_exhausted"
        assert queue.last_error == "keep me"
        assert queue.next_attempt_at is not None
        assert queue.next_attempt_at.replace(tzinfo=timezone.utc) == future
        sentinel = session.query(FullTextSourceAttempt).one()
        assert sentinel.source_kind == "paper_search_mcp_search"
        assert sentinel.failure_kind == "no_match"
