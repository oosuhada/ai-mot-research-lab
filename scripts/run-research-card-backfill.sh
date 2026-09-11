#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CLI="$ROOT_DIR/apps/api/.venv-prod/bin/research-lab"
PYTHON="$ROOT_DIR/apps/api/.venv-prod/bin/python"
ARTIFACT_DIR="$ROOT_DIR/artifacts/research-cards"
LOCK_DIR="$ARTIFACT_DIR/.backfill-lock"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://research:research@127.0.0.1:55432/research_lab}"

mkdir -p "$ARTIFACT_DIR"

if [[ ! -x "$PYTHON" || ! -x "$CLI" ]]; then
  echo "Research-card backfill cannot start: production API venv is missing." >&2
  exit 75
fi

acquire_lock() {
  if mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "$$" > "$LOCK_DIR/pid"
    return 0
  fi
  local owner=""
  if [[ -r "$LOCK_DIR/pid" ]]; then
    owner="$(<"$LOCK_DIR/pid")"
  fi
  if [[ "$owner" == <-> ]] && kill -0 "$owner" 2>/dev/null; then
    echo '{"status":"skipped","reason":"lock_exists"}'
    return 1
  fi
  rm -rf "$LOCK_DIR"
  mkdir "$LOCK_DIR"
  echo "$$" > "$LOCK_DIR/pid"
  echo '{"event":"stale_lock_recovered"}'
}

if ! acquire_lock; then
  exit 0
fi
trap 'rm -rf "$LOCK_DIR" 2>/dev/null || true' EXIT INT TERM

if ! "$PYTHON" - <<'PY'
import json
import os
import sys

from sqlalchemy import create_engine, text

max_active = int(os.environ.get("RESEARCH_CARD_BACKFILL_MAX_ACTIVE", "12"))
max_full_text_processing = int(os.environ.get("RESEARCH_CARD_BACKFILL_MAX_FULL_TEXT_PROCESSING", "100"))

try:
    engine = create_engine(
        os.environ["DATABASE_URL"],
        connect_args={"connect_timeout": 5},
        pool_pre_ping=True,
    )
    with engine.connect() as conn:
        conn.execute(text("SET statement_timeout = 5000"))
        active = int(conn.execute(text("""
            SELECT count(*)
            FROM pg_stat_activity
            WHERE datname = current_database()
              AND state = 'active'
              AND pid <> pg_backend_pid()
        """)).scalar() or 0)
        processing = int(conn.execute(text("""
            SELECT count(*)
            FROM full_text_queue
            WHERE status = 'processing'
        """)).scalar() or 0)
        snapshot = {
            "event": "database_backpressure_check",
            "active_queries": active,
            "full_text_processing": processing,
            "max_active_queries": max_active,
            "max_full_text_processing": max_full_text_processing,
        }
        print(json.dumps(snapshot, sort_keys=True))
        if active > max_active or processing > max_full_text_processing:
            print(json.dumps({"status": "skipped", "reason": "database_backpressure", **snapshot}, sort_keys=True))
            sys.exit(75)
except Exception as exc:
    print(json.dumps({"status": "skipped", "reason": "database_unavailable", "error_type": type(exc).__name__}))
    sys.exit(75)
PY
then
  exit 0
fi

"$CLI" backfill-research-cards \
  --limit "${RESEARCH_CARD_BACKFILL_LIMIT:-250}" \
  --min-year "${RESEARCH_CARD_BACKFILL_MIN_YEAR:-2018}" \
  --commit-every "${RESEARCH_CARD_BACKFILL_COMMIT_EVERY:-25}"

"$CLI" backfill-research-signal-extracts \
  --limit "${RESEARCH_SIGNAL_EXTRACT_BACKFILL_LIMIT:-500}"

"$CLI" refresh-signal-opportunities \
  --limit "${RESEARCH_SIGNAL_OPPORTUNITY_LIMIT:-24}" \
  --min-intersection "${RESEARCH_SIGNAL_OPPORTUNITY_MIN_INTERSECTION:-3}"

