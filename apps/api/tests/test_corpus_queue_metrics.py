from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from research_lab.corpus_intelligence import get_corpus_coverage, get_full_text_queue
from research_lab.models import Base, FullTextQueueItem, Paper, PaperChunk, PaperLocalization


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


def test_korean_metrics_separate_localization_and_full_text_intersection() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)

    with Session(engine) as session:
        translated_with_full_text = _paper("Translated with full text")
        translated_abstract_only = _paper("Translated abstract only")
        translated_title_only = _paper("Translated title only")
        full_text_only = _paper("Full text only")
        session.add_all([
            translated_with_full_text,
            translated_abstract_only,
            translated_title_only,
            full_text_only,
        ])
        session.flush()
        session.add_all([
            PaperLocalization(
                paper_id=translated_with_full_text.id,
                locale="ko",
                title="전문 있는 번역",
                abstract="전문도 확보된 초록 번역",
                keywords=["전문"],
                status="completed",
                source_hash="hash-1",
                translated_at=now,
            ),
            PaperLocalization(
                paper_id=translated_abstract_only.id,
                locale="ko",
                title="초록 번역",
                abstract="초록만 번역",
                keywords=[],
                status="completed",
                source_hash="hash-2",
                translated_at=now,
            ),
            PaperLocalization(
                paper_id=translated_title_only.id,
                locale="ko",
                title="제목만 번역",
                abstract=None,
                keywords=[],
                status="completed",
                source_hash="hash-3",
                translated_at=now,
            ),
            PaperChunk(
                paper_id=translated_with_full_text.id,
                source_locator="p.1",
                text="full text evidence",
                text_hash="chunk-1",
            ),
            PaperChunk(
                paper_id=full_text_only.id,
                source_locator="p.1",
                text="full text evidence without Korean",
                text_hash="chunk-2",
            ),
        ])
        session.commit()

        coverage = get_corpus_coverage(session)

        assert coverage.translated_ko == 3
        assert coverage.translated_ko_title == 3
        assert coverage.translated_ko_abstract == 2
        assert coverage.translated_ko_with_full_text == 1
        assert coverage.translated_ko_without_full_text == 2
        assert coverage.full_text_without_translated_ko == 1
