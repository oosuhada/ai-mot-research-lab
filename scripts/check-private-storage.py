#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from research_lab.config import Settings
from research_lab.storage_guard import PrivateStorageUnavailable, ensure_private_storage_ready

RETRY_HOURS = int(os.environ.get("PRIVATE_DATA_RETRY_HOURS", "24"))
STATE_PATH = Path(
    os.environ.get(
        "PRIVATE_DATA_RETRY_STATE",
        str(Path(__file__).resolve().parents[1] / "artifacts" / "storage" / "private-storage-retry.json"),
    )
)


def _read_retry_after() -> datetime | None:
    try:
        payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return datetime.fromisoformat(payload["retry_after"])
    except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError):
        return None


def _schedule_retry(reason: str, now: datetime) -> datetime:
    retry_after = now + timedelta(hours=RETRY_HOURS)
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(
            {
                "failed_at": now.isoformat(),
                "retry_after": retry_after.isoformat(),
                "retry_hours": RETRY_HOURS,
                "reason": reason,
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    return retry_after


def main() -> int:
    now = datetime.now(timezone.utc)
    retry_after = _read_retry_after()
    if retry_after is not None and now < retry_after:
        print(
            f"Private storage retry deferred until {retry_after.astimezone().isoformat(timespec="seconds")}",
            file=sys.stderr,
        )
        return 75

    settings = Settings()
    try:
        root = ensure_private_storage_ready(settings)
    except PrivateStorageUnavailable as exc:
        retry_after = _schedule_retry(str(exc), now)
        print(
            f"Private storage unavailable: {exc}; next retry after "
            f"{retry_after.astimezone().isoformat(timespec="seconds")}",
            file=sys.stderr,
        )
        return 75

    STATE_PATH.unlink(missing_ok=True)
    print(f"Private storage ready: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
