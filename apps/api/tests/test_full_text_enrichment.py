from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from research_lab.config import Settings
from research_lab.full_text_enrichment import FullTextEnrichmentWorker
from research_lab.models import FullTextQueueItem, Paper, PaperContentProfile
from research_lab.pdf_pipeline import PdfEvidenceService


def test_full_text_worker_processes_only_rights_safe_queue_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    for table in (Paper.__table__, PaperContentProfile.__table__, FullTextQueueItem.__table__):
        table.create(engine)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"%PDF-1.7\nqueue-test", request=request)

    def fake_ingest(*_args: object, **_kwargs: object) -> None:
        return None

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
