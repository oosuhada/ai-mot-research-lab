from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from research_lab.bulk_full_text import (
    PmcBulkFullTextWorker,
    _current_versioned_pmcid,
    _match_s2orc_record,
    _s2orc_text,
)
from research_lab.config import Settings
from research_lab.full_text_enrichment import FullTextEnrichmentWorker
from research_lab.models import (
    FullTextQueueItem,
    FullTextSourceAttempt,
    Paper,
    PaperChunk,
    PaperContentProfile,
)
from research_lab.pdf_pipeline import PdfEvidenceService
from research_lab.xml_pipeline import XmlEvidenceService


def _create_tables(engine: object) -> None:
    for table in (
        Paper.__table__,
        PaperChunk.__table__,
        PaperContentProfile.__table__,
        FullTextQueueItem.__table__,
        FullTextSourceAttempt.__table__,
    ):
        table.create(engine)  # type: ignore[arg-type]


def _queued_paper(session: Session, *, title: str, doi: str, arxiv_id: str | None = None) -> Paper:
    paper = Paper(
        title=title,
        doi=doi,
        arxiv_id=arxiv_id,
        is_oa=True,
        primary_source="openalex",
        source_record_id=title,
        retrieved_at=datetime.now(UTC),
        provenance={},
    )
    session.add(paper)
    session.flush()
    session.add_all(
        [
            PaperContentProfile(paper_id=paper.id, full_text_status="queued"),
            FullTextQueueItem(
                paper_id=paper.id,
                status="pending",
                priority=50,
                rights_status="open_access",
            ),
        ]
    )
    return paper


def test_pmc_bulk_worker_maps_many_dois_in_one_request_and_ingests_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    _create_tables(engine)
    mapping_requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal mapping_requests
        if "idconv" in str(request.url):
            mapping_requests += 1
            assert "10.1000%2Foa" in str(request.url)
            assert "10.1000%2Fmissing" in str(request.url)
            return httpx.Response(
                200,
                json={
                    "records": [
                        {"doi": "10.1000/oa", "pmcid": "PMC12345", "live": True},
                        {"doi": "10.1000/missing", "errmsg": "not found"},
                    ]
                },
                request=request,
            )
        return httpx.Response(200, content=b"<article><body><p>Full text</p></body></article>", request=request)

    monkeypatch.setattr(
        XmlEvidenceService,
        "ingest",
        lambda *_args, **_kwargs: SimpleNamespace(chunk_count=3, extraction_status="extracted"),
    )
    with Session(engine) as session:
        oa = _queued_paper(session, title="oa", doi="10.1000/oa")
        missing = _queued_paper(session, title="missing", doi="10.1000/missing")
        session.commit()

        result = PmcBulkFullTextWorker(
            session,
            Settings(database_url="sqlite+pysqlite:///:memory:"),
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        ).run(max_items=20, download_workers=2)

        assert mapping_requests == 1
        assert result == {
            "worker_id": result["worker_id"],
            "selected": 2,
            "mapped": 1,
            "completed": 1,
            "failed": 1,
        }
        assert (
            session.scalar(select(FullTextQueueItem).where(FullTextQueueItem.paper_id == oa.id)).status == "completed"
        )
        assert (
            session.scalar(select(FullTextQueueItem).where(FullTextQueueItem.paper_id == missing.id)).status
            == "pending"
        )
        assert session.query(FullTextSourceAttempt).count() == 2


def test_arxiv_source_lane_does_not_claim_general_paper(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    _create_tables(engine)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"%PDF-1.7\narxiv", request=request)

    monkeypatch.setattr(
        PdfEvidenceService,
        "ingest",
        lambda *_args, **_kwargs: SimpleNamespace(chunk_count=2, extraction_status="extracted"),
    )
    with Session(engine) as session:
        general = _queued_paper(session, title="general", doi="10.1000/general")
        arxiv = _queued_paper(
            session,
            title="arxiv",
            doi="10.48550/arxiv.2401.12345",
            arxiv_id="2401.12345",
        )
        session.commit()

        result = FullTextEnrichmentWorker(
            session,
            Settings(database_url="sqlite+pysqlite:///:memory:"),
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        ).run(max_items=1, source_lane="arxiv")

        assert result["completed"] == 1
        assert result["source_lane"] == "arxiv"
        assert (
            session.scalar(select(FullTextQueueItem).where(FullTextQueueItem.paper_id == arxiv.id)).status
            == "completed"
        )
        assert (
            session.scalar(select(FullTextQueueItem).where(FullTextQueueItem.paper_id == general.id)).status
            == "pending"
        )


def test_s2orc_helpers_match_external_doi_and_extract_body_text() -> None:
    paper = SimpleNamespace(doi="10.1000/s2orc", arxiv_id=None, s2_id=None)
    lookup = {"doi": {"10.1000/s2orc": paper}, "arxiv": {}, "s2": {}}
    record = {
        "externalIds": {"DOI": "https://doi.org/10.1000/S2ORC"},
        "body_text": [{"section": "Intro", "text": "One"}, {"section": "Methods", "text": "Two"}],
    }

    assert _match_s2orc_record(record, lookup) is paper
    assert _s2orc_text(json.loads(json.dumps(record))) == "One\n\nTwo"


def test_pmc_bulk_prefers_current_version_for_world_readable_s3_object() -> None:
    assert (
        _current_versioned_pmcid(
            {
                "pmcid": "PMC123",
                "versions": [
                    {"pmcid": "PMC123.1", "current": False},
                    {"pmcid": "PMC123.2", "current": True},
                ],
            }
        )
        == "PMC123.2"
    )
