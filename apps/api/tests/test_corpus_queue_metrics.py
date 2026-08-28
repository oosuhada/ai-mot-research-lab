from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from research_lab.corpus_intelligence import get_corpus_coverage, get_full_text_queue
from research_lab.models import Base, FullTextQueueItem, Paper


def _paper(title: str) -> Paper:
    return Paper(
        title=title,
        primary_source="test",
        source_record_id=title.lower().replace(" ", "-"),
        retrieved_at=datetime.now(UTC),
        provenance={},
    )


def test_queue_metrics_separate_ready_deferred_processing_and_recent_completion() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)

    with Session(engine) as session:
        papers = [_paper(f"Paper {index}") for index in range(5)]
        session.add_all(papers)
        session.flush()
        session.add_all(
            [
                FullTextQueueItem(
                    paper_id=papers[0].id,
                    status="pending",
                    rights_status="open_access",
                    reason_factors={},
                ),
                FullTextQueueItem(
                    paper_id=papers[1].id,
                    status="pending",
                    rights_status="open_access",
                    next_attempt_at=now + timedelta(hours=1),
                    reason_factors={},
                ),
                FullTextQueueItem(
                    paper_id=papers[2].id,
                    status="processing",
                    rights_status="open_access",
                    reason_factors={},
                ),
                FullTextQueueItem(
                    paper_id=papers[3].id,
                    status="completed",
                    rights_status="open_access",
                    updated_at=now - timedelta(hours=1),
                    reason_factors={},
                ),
                FullTextQueueItem(
                    paper_id=papers[4].id,
                    status="completed",
                    rights_status="open_access",
                    updated_at=now - timedelta(days=2),
                    reason_factors={},
                ),
            ]
        )
        session.commit()

        coverage = get_corpus_coverage(session)
        queue = get_full_text_queue(session)

        assert coverage.full_text_queued == 3
        assert coverage.full_text_claimable == 1
        assert coverage.full_text_deferred == 1
        assert coverage.full_text_processing == 1
        assert coverage.full_text_completed_24h == 1
        assert queue.pending == 2
        assert queue.processing == 1
        assert queue.claimable == 1
        assert queue.deferred == 1
        assert queue.completed_24h == 1
        assert queue.completed == 2
