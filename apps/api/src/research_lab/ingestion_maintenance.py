from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from research_lab.models import IngestionRun


@dataclass(slots=True)
class StaleRunSweepResult:
    scanned: int = 0
    abandoned: int = 0
    failed_timeout: int = 0
    kept_running: int = 0
    by_source: dict[str, dict[str, int]] = field(default_factory=dict)


def _parse_activity_timestamp(checkpoint: dict[str, Any]) -> datetime | None:
    for key in ("heartbeat_at", "updated_at"):
        value = checkpoint.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    return None


def _bump_source(result: StaleRunSweepResult, source: str, status: str) -> None:
    bucket = result.by_source.setdefault(
        source,
        {"abandoned": 0, "failed_timeout": 0, "kept_running": 0},
    )
    bucket[status] += 1


def sweep_stale_ingestion_runs(
    session: Session,
    *,
    heartbeat_timeout_hours: float = 6.0,
    no_heartbeat_timeout_hours: float = 24.0,
    now: datetime | None = None,
    dry_run: bool = False,
) -> StaleRunSweepResult:
    if heartbeat_timeout_hours <= 0:
        raise ValueError("heartbeat_timeout_hours must be greater than zero")
    if no_heartbeat_timeout_hours <= 0:
        raise ValueError("no_heartbeat_timeout_hours must be greater than zero")

    current = (now or datetime.now(UTC)).astimezone(UTC)
    heartbeat_cutoff = current - timedelta(hours=heartbeat_timeout_hours)
    no_heartbeat_cutoff = current - timedelta(hours=no_heartbeat_timeout_hours)
    rows = session.scalars(
        select(IngestionRun)
        .where(IngestionRun.status == "running")
        .order_by(IngestionRun.started_at.asc())
    ).all()

    result = StaleRunSweepResult(scanned=len(rows))
    for run in rows:
        checkpoint = dict(run.checkpoint or {})
        activity_at = _parse_activity_timestamp(checkpoint)
        started_at = run.started_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=UTC)
        else:
            started_at = started_at.astimezone(UTC)

        target_status: str | None = None
        reason: str | None = None
        if activity_at is not None and activity_at <= heartbeat_cutoff:
            target_status = "failed_timeout"
            reason = (
                f"ingestion heartbeat stale for at least {heartbeat_timeout_hours:g} hours; "
                f"last activity {activity_at.isoformat()}"
            )
        elif activity_at is None and started_at <= no_heartbeat_cutoff:
            target_status = "abandoned"
            reason = (
                f"ingestion run had no heartbeat and exceeded {no_heartbeat_timeout_hours:g} hours; "
                f"started {started_at.isoformat()}"
            )

        if target_status is None:
            result.kept_running += 1
            _bump_source(result, run.source, "kept_running")
            continue

        if target_status == "failed_timeout":
            result.failed_timeout += 1
        else:
            result.abandoned += 1
        _bump_source(result, run.source, target_status)

        if dry_run:
            continue

        maintenance = dict(checkpoint.get("maintenance") or {})
        maintenance.update(
            {
                "finalized_by": "stale_ingestion_sweep",
                "finalized_at": current.isoformat(),
                "previous_status": "running",
                "status": target_status,
                "reason": reason,
            }
        )
        checkpoint["maintenance"] = maintenance
        run.checkpoint = checkpoint
        run.status = target_status
        run.finished_at = current
        existing_error = (run.error_message or "").strip()
        run.error_message = f"{existing_error}\n{reason}".strip() if existing_error else reason
        if target_status == "failed_timeout":
            run.error_count += 1

    if not dry_run:
        session.commit()
    return result

