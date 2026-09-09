from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from research_lab.config import Settings
from research_lab.models import Base, FullTextQueueItem, IngestionRun, Paper, PaperContentProfile
from research_lab.semantic_scholar_fast import SemanticScholarBatchMapper
from research_lab.taxonomy import TAXONOMY_VERSION


def _paper() -> Paper:
    return Paper(
        doi="10.1000/example",
        title="Example",
        publication_year=2025,
        work_type="article",
        is_oa=False,
        retraction_status="none",
        correction_status="none",
        primary_source="openalex",
        source_record_id="W1",
        retrieved_at=datetime.now(UTC),
        provenance={},
    )


def test_batch_mapper_backfills_ids_and_reactivates_oa_queue() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/paper/batch")
        assert request.url.params["fields"].startswith("paperId,corpusId")
        return httpx.Response(
            200,
            json=[
                {
                    "paperId": "a" * 40,
                    "corpusId": 12345,
                    "externalIds": {"DOI": "10.1000/example"},
                    "isOpenAccess": True,
                    "openAccessPdf": {
                        "url": "https://example.test/paper.pdf",
                        "status": "GOLD",
                        "license": "CCBY",
                    },
                    "citationCount": 9,
                    "referenceCount": 4,
                }
            ],
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with Session(engine) as session:
        paper = _paper()
        session.add(paper)
        session.flush()
        session.add(
            PaperContentProfile(
                paper_id=paper.id,
                abstract_status="available",
                full_text_status="failed",
                full_text_access="unknown",
                rights_status="unknown",
                full_text_priority=10,
            )
        )
        session.add(
            FullTextQueueItem(
                paper_id=paper.id,
                status="failed",
                priority=10,
                rights_status="unknown",
                failure_kind="source_exhausted",
                last_error="no source",
            )
        )
        session.commit()

        result = SemanticScholarBatchMapper(
            session,
            Settings(semantic_scholar_api_key="test-key", _env_file=None),
            client=client,
            min_interval_seconds=0,
        ).run(batch_size=500)
        paper = session.scalar(select(Paper))
        profile = session.scalar(select(PaperContentProfile))
        queue = session.scalar(select(FullTextQueueItem))

    assert result.selected == 1
    assert result.requests == 1
    assert result.found == 1
    assert result.updated == 1
    assert result.oa_pdf_discovered == 1
    assert result.queue_reactivated == 1
    assert paper is not None
    assert paper.s2_id == "a" * 40
    assert paper.s2_corpus_id == "12345"
    assert paper.pdf_url == "https://example.test/paper.pdf"
    assert paper.is_oa is True
    assert profile is not None
    assert profile.rights_status == "open_access"
    assert profile.full_text_status == "queued"
    assert profile.full_text_priority == 95
    assert queue is not None
    assert queue.status == "pending"
    assert queue.rights_status == "open_access"
    assert queue.priority == 95
    assert queue.failure_kind is None


def test_oa_enrichment_uses_existing_s2_id_and_accelerates_pending_pdf() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.url.path.endswith("/paper/batch")
        assert request.read().decode().count("a" * 40) == 1
        return httpx.Response(
            200,
            json=[
                {
                    "paperId": "a" * 40,
                    "corpusId": 12345,
                    "externalIds": {"DOI": "10.1000/example"},
                    "isOpenAccess": True,
                    "openAccessPdf": {"url": "https://example.test/direct.pdf"},
                    "citationCount": 3,
                    "referenceCount": 2,
                }
            ],
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with Session(engine) as session:
        paper = _paper()
        paper.s2_id = "a" * 40
        paper.s2_corpus_id = "12345"
        session.add(paper)
        session.flush()
        session.add(
            PaperContentProfile(
                paper_id=paper.id,
                abstract_status="available",
                full_text_status="queued",
                full_text_access="unknown",
                rights_status="unknown",
                full_text_priority=30,
            )
        )
        session.add(
            FullTextQueueItem(
                paper_id=paper.id,
                status="pending",
                priority=30,
                rights_status="unknown",
                failure_kind="temporarily_unavailable",
                last_error="retry later",
                next_attempt_at=datetime.now(UTC) + timedelta(days=1),
            )
        )
        session.commit()

        mapper = SemanticScholarBatchMapper(
            session,
            Settings(semantic_scholar_api_key="test-key", _env_file=None),
            client=client,
            min_interval_seconds=0,
        )
        result = mapper.enrich_mapped_oa(max_items=10, refresh_days=30)
        paper = session.scalar(select(Paper))
        profile = session.scalar(select(PaperContentProfile))
        queue = session.scalar(select(FullTextQueueItem))

    assert calls == 1
    assert result.selected == 1
    assert result.found == 1
    assert result.oa_pdf_discovered == 1
    assert result.queue_reactivated == 1
    assert paper is not None
    assert paper.pdf_url == "https://example.test/direct.pdf"
    assert paper.is_oa is True
    assert paper.provenance.get("semantic_scholar_oa_checked_at")
    assert profile is not None
    assert profile.rights_status == "open_access"
    assert profile.full_text_priority == 95
    assert queue is not None
    assert queue.status == "pending"
    assert queue.rights_status == "open_access"
    assert queue.priority == 95
    assert queue.failure_kind is None
    assert queue.last_error is None
    assert queue.next_attempt_at is not None
    next_attempt_at = queue.next_attempt_at
    if next_attempt_at.tzinfo is None:
        next_attempt_at = next_attempt_at.replace(tzinfo=UTC)
    assert next_attempt_at <= datetime.now(UTC)


def test_oa_enrichment_skips_recently_checked_paper() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    def handler(_: httpx.Request) -> httpx.Response:
        raise AssertionError("recent OA check should not make a network request")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with Session(engine) as session:
        paper = _paper()
        paper.s2_id = "b" * 40
        paper.provenance = {
            "semantic_scholar_oa_checked_at": datetime.now(UTC).isoformat(),
        }
        session.add(paper)
        session.commit()
        result = SemanticScholarBatchMapper(
            session,
            Settings(semantic_scholar_api_key="test-key", _env_file=None),
            client=client,
            min_interval_seconds=0,
        ).enrich_mapped_oa(max_items=10, refresh_days=30)

    assert result.selected == 0
    assert result.requests == 0


def test_batch_mapper_rejects_mismatched_external_identity() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "paperId": "b" * 40,
                    "corpusId": 999,
                    "externalIds": {"DOI": "10.1000/different"},
                    "isOpenAccess": False,
                    "openAccessPdf": None,
                }
            ],
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with Session(engine) as session:
        session.add(_paper())
        session.commit()
        result = SemanticScholarBatchMapper(
            session,
            Settings(semantic_scholar_api_key="test-key", _env_file=None),
            client=client,
            min_interval_seconds=0,
        ).run()
        paper = session.scalar(select(Paper))

    assert result.conflicts == 1
    assert result.updated == 0
    assert paper is not None
    assert paper.s2_id is None
    assert paper.s2_corpus_id is None


def test_batch_mapper_survives_more_than_eight_rate_limits() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    attempts = 0
    sleeps: list[float] = []

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts <= 10:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(
            200,
            json=[
                {
                    "paperId": "c" * 40,
                    "corpusId": 777,
                    "externalIds": {"DOI": "10.1000/example"},
                    "isOpenAccess": False,
                    "openAccessPdf": None,
                }
            ],
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with Session(engine) as session:
        session.add(_paper())
        session.commit()
        result = SemanticScholarBatchMapper(
            session,
            Settings(semantic_scholar_api_key="test-key", _env_file=None),
            client=client,
            min_interval_seconds=0,
            sleep=sleeps.append,
        ).run()

    assert attempts == 11
    assert len(sleeps) == 10
    assert result.status == "completed"
    assert result.updated == 1


def test_batch_mapper_marks_interrupted_prior_run_failed() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "paperId": "d" * 40,
                    "corpusId": 888,
                    "externalIds": {"DOI": "10.1000/example"},
                    "isOpenAccess": False,
                    "openAccessPdf": None,
                }
            ],
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with Session(engine) as session:
        interrupted = IngestionRun(
            source="semantic_scholar_batch_api",
            status="running",
            taxonomy_version=TAXONOMY_VERSION,
            query_spec={},
            checkpoint={"processed": 500},
        )
        session.add_all([_paper(), interrupted])
        session.commit()
        interrupted_id = interrupted.id

        result = SemanticScholarBatchMapper(
            session,
            Settings(semantic_scholar_api_key="test-key", _env_file=None),
            client=client,
            min_interval_seconds=0,
        ).run()
        recovered = session.get(IngestionRun, interrupted_id)

    assert result.status == "completed"
    assert recovered is not None
    assert recovered.status == "failed"
    assert recovered.finished_at is not None
    assert recovered.error_message == "Recovered after interrupted Semantic Scholar batch mapper process"


def test_batch_mapper_splits_400_batch_and_skips_only_bad_identifier() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    def handler(request: httpx.Request) -> httpx.Response:
        ids = request.read().decode()
        if "DOI:bad" in ids and "DOI:10.1000/example" in ids:
            return httpx.Response(400)
        if "DOI:bad" in ids:
            return httpx.Response(400)
        return httpx.Response(
            200,
            json=[
                {
                    "paperId": "e" * 40,
                    "corpusId": 999,
                    "externalIds": {"DOI": "10.1000/example"},
                    "isOpenAccess": False,
                    "openAccessPdf": None,
                }
            ],
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with Session(engine) as session:
        mapper = SemanticScholarBatchMapper(
            session,
            Settings(semantic_scholar_api_key="test-key", _env_file=None),
            client=client,
            min_interval_seconds=0,
            sleep=lambda _: None,
        )
        result = mapper._request_batch(["DOI:bad", "DOI:10.1000/example"])

    assert result[0] is None
    assert result[1] is not None
    assert result[1]["corpusId"] == 999


def test_batch_mapper_bounds_bad_request_splitting() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(400)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with Session(engine) as session:
        mapper = SemanticScholarBatchMapper(
            session,
            Settings(semantic_scholar_api_key="test-key", _env_file=None),
            client=client,
            min_interval_seconds=0,
            sleep=lambda _: None,
            max_bad_request_split_depth=1,
        )
        records = mapper._request_batch([f"DOI:bad-{index}" for index in range(8)])

    assert records == [None] * 8
    assert calls == 3
    assert mapper._bad_request_groups_skipped == 2


def test_batch_mapper_stops_hard_tail_and_cools_down_followup_run() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(400)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with Session(engine) as session:
        papers = []
        for index in range(500):
            paper = _paper()
            paper.doi = f"10.1000/hard-tail-{index}"
            paper.source_record_id = f"W{index + 1000}"
            papers.append(paper)
        session.add_all(papers)
        session.commit()

        first = SemanticScholarBatchMapper(
            session,
            Settings(semantic_scholar_api_key="test-key", _env_file=None),
            client=client,
            min_interval_seconds=0,
            sleep=lambda _: None,
            max_bad_request_split_depth=1,
            hard_tail_min_candidates=500,
            hard_tail_probe_batches=1,
            hard_tail_min_hit_rate=0.05,
        ).run(batch_size=500)

        calls_after_first = calls
        second = SemanticScholarBatchMapper(
            session,
            Settings(semantic_scholar_api_key="test-key", _env_file=None),
            client=client,
            min_interval_seconds=0,
            sleep=lambda _: None,
            max_bad_request_split_depth=1,
            hard_tail_min_candidates=500,
        ).run(batch_size=500)

    assert first.status == "completed"
    assert first.processed == 500
    assert first.circuit_breaker_triggered is True
    assert first.stop_reason == "hard_tail_low_hit_rate"
    assert first.bad_request_groups_skipped == 2
    assert first.requests == 3
    assert calls_after_first == 3
    assert second.status == "completed"
    assert second.processed == 0
    assert second.circuit_breaker_triggered is True
    assert second.stop_reason == "hard_tail_cooldown_active"
    assert second.requests == 0
    assert calls == calls_after_first
