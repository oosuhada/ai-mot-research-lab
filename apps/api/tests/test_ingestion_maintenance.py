from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from research_lab.ingestion_maintenance import sweep_stale_ingestion_runs
from research_lab.models import Base, IngestionRun


def _run(
    *,
    source: str,
    started_at: datetime,
    checkpoint: dict[str, object] | None = None,
) -> IngestionRun:
    return IngestionRun(
        source=source,
        status="running",
        taxonomy_version="test",
        query_spec={},
        checkpoint=checkpoint or {},
        started_at=started_at,
    )


def test_sweep_marks_old_no_heartbeat_run_abandoned_and_keeps_recent_run() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime(2026, 9, 6, 0, 0, tzinfo=UTC)
    with Session(engine) as session:
        session.add_all(
            [
                _run(source="old", started_at=now - timedelta(hours=30)),
                _run(source="recent", started_at=now - timedelta(hours=5)),
            ]
        )
        session.commit()

        result = sweep_stale_ingestion_runs(session, now=now)

        rows = {row.source: row for row in session.scalars(select(IngestionRun)).all()}
        assert result.abandoned == 1
        assert result.failed_timeout == 0
        assert result.kept_running == 1
        assert rows["old"].status == "abandoned"
        assert rows["old"].finished_at is not None
        assert rows["old"].finished_at.replace(tzinfo=UTC) == now
        assert rows["old"].checkpoint["maintenance"]["finalized_by"] == "stale_ingestion_sweep"
        assert rows["recent"].status == "running"


def test_sweep_marks_stale_heartbeat_failed_timeout() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime(2026, 9, 6, 0, 0, tzinfo=UTC)
    with Session(engine) as session:
        session.add(
            _run(
                source="heartbeat-worker",
                started_at=now - timedelta(hours=12),
                checkpoint={"updated_at": (now - timedelta(hours=7)).isoformat()},
            )
        )
        session.commit()

        result = sweep_stale_ingestion_runs(session, now=now)
        row = session.scalar(select(IngestionRun))

        assert result.failed_timeout == 1
        assert row is not None
        assert row.status == "failed_timeout"
        assert row.error_count == 1
        assert "heartbeat stale" in (row.error_message or "")


def test_sweep_dry_run_does_not_modify_rows() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime(2026, 9, 6, 0, 0, tzinfo=UTC)
    with Session(engine) as session:
        session.add(_run(source="old", started_at=now - timedelta(hours=48)))
        session.commit()

        result = sweep_stale_ingestion_runs(session, now=now, dry_run=True)
        row = session.scalar(select(IngestionRun))

        assert result.abandoned == 1
        assert row is not None
        assert row.status == "running"
        assert row.finished_at is None
