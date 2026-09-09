#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$ROOT_DIR/apps/api/.venv-prod/bin/python"
CLI="$ROOT_DIR/apps/api/.venv-prod/bin/research-lab"
TIMEOUT="$ROOT_DIR/scripts/run-command-with-timeout.py"
LOCK_DIR="${PRO_FULL_TEXT_LOCK_DIR:-/tmp/ai-mot-pro-full-text-aggressive.lock}"
TUNNEL_SOCKET="${PRO_FULL_TEXT_TUNNEL_SOCKET:-/tmp/ai-mot-mini-db-tunnel.sock}"
MINI_HOST="${PRO_FULL_TEXT_MINI_HOST:-mac-mini}"
MINI_DB_PORT="${PRO_FULL_TEXT_MINI_DB_PORT:-55432}"
LOCAL_DB_PORT="${PRO_FULL_TEXT_LOCAL_DB_PORT:-55432}"
WORKER_TIMEOUT_SECONDS="${PRO_FULL_TEXT_WORKER_TIMEOUT_SECONDS:-1080}"
PRIVATE_ROOT="${PRIVATE_DATA_ROOT:-$HOME/Library/Caches/oosu-ai-mot-research-lab/private}"

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo '{"status":"skipped","reason":"lock_exists"}'
  exit 0
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

mkdir -p "$ROOT_DIR/artifacts/full-text/pro" "$PRIVATE_ROOT"

if [[ ! -x "$PYTHON" || ! -x "$CLI" ]]; then
  echo "Pro full-text venv is missing; bootstrap apps/api/.venv-prod before scheduling this worker." >&2
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
export PRIVATE_DATA_MIN_FREE_GB="${PRIVATE_DATA_MIN_FREE_GB:-35}"

"$PYTHON" "$ROOT_DIR/scripts/check-private-storage.py" >/dev/null

worker_pids=()
overall_status=0

run_worker() {
  local lane_name="$1"
  shift
  "$PYTHON" "$TIMEOUT" --timeout-seconds "$WORKER_TIMEOUT_SECONDS" -- "$CLI" "$@" &
  worker_pids+=("$!")
  echo "{\"event\":\"worker_started\",\"lane\":\"${lane_name}\",\"pid\":${worker_pids[-1]}}"
}

PMC_MAX_ITEMS="${PRO_FULL_TEXT_PMC_MAX_ITEMS:-80}"
PMC_DOWNLOAD_WORKERS="${PRO_FULL_TEXT_PMC_DOWNLOAD_WORKERS:-6}"
ARXIV_MAX_ITEMS="${PRO_FULL_TEXT_ARXIV_MAX_ITEMS:-0}"
DIRECT_WORKERS="${PRO_FULL_TEXT_DIRECT_WORKERS:-6}"
OA_WORKERS="${PRO_FULL_TEXT_OA_WORKERS:-2}"
ANY_WORKERS="${PRO_FULL_TEXT_ANY_WORKERS:-2}"

if (( PMC_MAX_ITEMS > 0 )); then
  run_worker pmc-bulk enrich-full-text-pmc-bulk \
    --max-items "$PMC_MAX_ITEMS" \
    --download-workers "$PMC_DOWNLOAD_WORKERS" \
    --max-xml-bytes 30000000 \
    --lease-minutes 20 \
    --worker-id "pro:pmc-bulk:${HOST:-pro}:$$"
fi

if (( ARXIV_MAX_ITEMS > 0 )); then
  run_worker arxiv enrich-full-text \
    --source-lane arxiv \
    --max-items "$ARXIV_MAX_ITEMS" \
    --max-pdf-bytes 30000000 \
    --lease-minutes 20 \
    --worker-id "pro:arxiv:${HOST:-pro}:$$"
fi

for (( worker_index = 1; worker_index <= DIRECT_WORKERS; worker_index++ )); do
  run_worker "direct-${worker_index}" enrich-full-text \
    --source-lane direct \
    --max-items "${PRO_FULL_TEXT_DIRECT_MAX_ITEMS:-35}" \
    --max-pdf-bytes 30000000 \
    --lease-minutes 20 \
    --worker-id "pro:direct:${HOST:-pro}:$$:${worker_index}"
done

for (( worker_index = 1; worker_index <= OA_WORKERS; worker_index++ )); do
  run_worker "oa-${worker_index}" enrich-full-text \
    --source-lane oa \
    --max-items "${PRO_FULL_TEXT_OA_MAX_ITEMS:-30}" \
    --max-pdf-bytes 30000000 \
    --lease-minutes 20 \
    --worker-id "pro:oa:${HOST:-pro}:$$:${worker_index}"
done

for (( worker_index = 1; worker_index <= ANY_WORKERS; worker_index++ )); do
  run_worker "any-${worker_index}" enrich-full-text \
    --source-lane any \
    --max-items "${PRO_FULL_TEXT_ANY_MAX_ITEMS:-24}" \
    --max-pdf-bytes 30000000 \
    --lease-minutes 20 \
    --worker-id "pro:any:${HOST:-pro}:$$:${worker_index}"
done

for worker_pid in "${worker_pids[@]}"; do
  wait "$worker_pid" || overall_status=$?
done

exit "$overall_status"
