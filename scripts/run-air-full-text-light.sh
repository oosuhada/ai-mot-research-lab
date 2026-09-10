#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$ROOT_DIR/apps/api/.venv-prod/bin/python"
CLI="$ROOT_DIR/apps/api/.venv-prod/bin/research-lab"
TIMEOUT="$ROOT_DIR/scripts/run-command-with-timeout.py"
LOCK_DIR="${AIR_FULL_TEXT_LOCK_DIR:-/tmp/ai-mot-air-full-text-light.lock}"
TUNNEL_SOCKET="${AIR_FULL_TEXT_TUNNEL_SOCKET:-/tmp/ai-mot-air-mini-db-tunnel.sock}"
MINI_HOST="${AIR_FULL_TEXT_MINI_HOST:-mac-mini}"
MINI_DB_PORT="${AIR_FULL_TEXT_MINI_DB_PORT:-55432}"
LOCAL_DB_PORT="${AIR_FULL_TEXT_LOCAL_DB_PORT:-55434}"
WORKER_TIMEOUT_SECONDS="${AIR_FULL_TEXT_WORKER_TIMEOUT_SECONDS:-720}"
PRIVATE_ROOT="${PRIVATE_DATA_ROOT:-$HOME/Library/Caches/oosu-ai-mot-research-lab/private}"

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  if pgrep -f "run-air-full-text-light.sh|air:direct:|air:oa:|air:any:" >/dev/null 2>&1; then
    echo '{"status":"skipped","reason":"lock_exists"}'
    exit 0
  fi
  rm -rf "$LOCK_DIR"
  if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    echo '{"status":"skipped","reason":"lock_exists_after_stale_recovery"}'
    exit 0
  fi
  echo '{"event":"stale_lock_recovered"}'
fi
echo "$$" > "$LOCK_DIR/pid"
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

mkdir -p "$ROOT_DIR/artifacts/full-text/air" "$PRIVATE_ROOT"

if [[ ! -x "$PYTHON" || ! -x "$CLI" ]]; then
  echo "Air full-text venv is missing; bootstrap apps/api/.venv-prod before scheduling this worker." >&2
  exit 75
fi

ensure_tunnel() {
  if nc -z 127.0.0.1 "$LOCAL_DB_PORT" >/dev/null 2>&1; then
    return 0
  fi
  ssh -S "$TUNNEL_SOCKET" -O exit "$MINI_HOST" >/dev/null 2>&1 || true
  rm -f "$TUNNEL_SOCKET"
  ssh -fN -M -S "$TUNNEL_SOCKET" \
    -o ExitOnForwardFailure=yes \
    -L "127.0.0.1:${LOCAL_DB_PORT}:127.0.0.1:${MINI_DB_PORT}" \
    "$MINI_HOST"
  for _attempt in {1..20}; do
    if nc -z 127.0.0.1 "$LOCAL_DB_PORT" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.5
  done
  echo "Mini DB tunnel did not become ready." >&2
  return 1
}

ensure_tunnel

export DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://research:research@127.0.0.1:${LOCAL_DB_PORT}/research_lab}"
export PRIVATE_DATA_ROOT="$PRIVATE_ROOT"
export PRIVATE_DATA_REQUIRE_EXTERNAL="false"
export PRIVATE_DATA_MIN_FREE_GB="${PRIVATE_DATA_MIN_FREE_GB:-20}"

"$PYTHON" "$ROOT_DIR/scripts/check-private-storage.py" >/dev/null

if ! "$PYTHON" - <<'PY'
import os
import sys

from sqlalchemy import create_engine, text

try:
    engine = create_engine(
        os.environ["DATABASE_URL"],
        connect_args={"connect_timeout": 5},
        pool_pre_ping=True,
    )
    with engine.connect() as conn:
        conn.execute(text("SET statement_timeout = 5000"))
        conn.execute(text("SELECT 1"))
except Exception as exc:
    print(f'{{"status":"skipped","reason":"database_unavailable","error_type":"{type(exc).__name__}"}}')
    sys.exit(75)
PY
then
  exit 0
fi

worker_pids=()
overall_status=0

run_worker() {
  local lane_name="$1"
  shift
  "$PYTHON" "$TIMEOUT" --timeout-seconds "$WORKER_TIMEOUT_SECONDS" -- "$CLI" "$@" &
  worker_pids+=("$!")
  echo "{\"event\":\"worker_started\",\"lane\":\"${lane_name}\",\"pid\":${worker_pids[-1]}}"
}

DIRECT_WORKERS="${AIR_FULL_TEXT_DIRECT_WORKERS:-1}"
OA_WORKERS="${AIR_FULL_TEXT_OA_WORKERS:-1}"
ANY_WORKERS="${AIR_FULL_TEXT_ANY_WORKERS:-0}"

for (( worker_index = 1; worker_index <= DIRECT_WORKERS; worker_index++ )); do
  run_worker "direct-${worker_index}" enrich-full-text \
    --source-lane direct \
    --max-items "${AIR_FULL_TEXT_DIRECT_MAX_ITEMS:-20}" \
    --max-pdf-bytes 30000000 \
    --lease-minutes 15 \
    --worker-id "air:direct:${HOST:-air}:$$:${worker_index}"
done

for (( worker_index = 1; worker_index <= OA_WORKERS; worker_index++ )); do
  run_worker "oa-${worker_index}" enrich-full-text \
    --source-lane oa \
    --max-items "${AIR_FULL_TEXT_OA_MAX_ITEMS:-16}" \
    --max-pdf-bytes 30000000 \
    --lease-minutes 15 \
    --worker-id "air:oa:${HOST:-air}:$$:${worker_index}"
done

for (( worker_index = 1; worker_index <= ANY_WORKERS; worker_index++ )); do
  run_worker "any-${worker_index}" enrich-full-text \
    --source-lane any \
    --max-items "${AIR_FULL_TEXT_ANY_MAX_ITEMS:-12}" \
    --max-pdf-bytes 30000000 \
    --lease-minutes 15 \
    --worker-id "air:any:${HOST:-air}:$$:${worker_index}"
done

for worker_pid in "${worker_pids[@]}"; do
  wait "$worker_pid" || overall_status=$?
done

exit "$overall_status"
