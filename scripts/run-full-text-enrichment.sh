#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CLI="$ROOT_DIR/apps/api/.venv-prod/bin/research-lab"
PYTHON="$ROOT_DIR/apps/api/.venv-prod/bin/python"
TIMEOUT="$ROOT_DIR/scripts/run-command-with-timeout.py"
if ! "$PYTHON" "$ROOT_DIR/scripts/check-private-storage.py"; then
  echo "Skipping full-text job because private storage is unavailable or below reserve." >&2
  exit 0
fi

UID_VALUE="$(id -u)"
REGULAR_WORKER_COUNT="${FULL_TEXT_REGULAR_WORKERS:-4}"
OA_WORKER_COUNT="${FULL_TEXT_OA_WORKERS:-2}"
DIRECT_WORKER_COUNT="${FULL_TEXT_DIRECT_WORKERS:-0}"
MAX_ITEMS_PER_WORKER="${FULL_TEXT_ENRICHMENT_MAX_ITEMS_PER_WORKER:-8}"
WORKER_TIMEOUT_SECONDS="${FULL_TEXT_WORKER_TIMEOUT_SECONDS:-720}"
TOOLS_DIR="${FULL_TEXT_BOOSTER_TOOLS_DIR:-$HOME/.local/share/ai-mot-research-lab/full-text-booster-tools}"


case "$REGULAR_WORKER_COUNT" in
  0|1|2|3|4) ;;
  *)
    echo "FULL_TEXT_REGULAR_WORKERS must be between 0 and 4." >&2
    exit 2
    ;;
esac

if ! [[ "$OA_WORKER_COUNT" == <-> ]] || (( OA_WORKER_COUNT < 0 || OA_WORKER_COUNT > REGULAR_WORKER_COUNT )); then
  echo "FULL_TEXT_OA_WORKERS must be between 0 and FULL_TEXT_REGULAR_WORKERS." >&2
  exit 2
fi

case "$DIRECT_WORKER_COUNT" in
  0|1|2|3|4) ;;
  *)
    echo "FULL_TEXT_DIRECT_WORKERS must be between 0 and 4." >&2
    exit 2
    ;;
esac

if (( REGULAR_WORKER_COUNT + DIRECT_WORKER_COUNT < 1 || REGULAR_WORKER_COUNT + DIRECT_WORKER_COUNT > 4 )); then
  echo "The combined regular and direct worker count must be between 1 and 4." >&2
  exit 2
fi

if ! [[ "$MAX_ITEMS_PER_WORKER" == <-> ]] || (( MAX_ITEMS_PER_WORKER < 1 || MAX_ITEMS_PER_WORKER > 50 )); then
  echo "FULL_TEXT_ENRICHMENT_MAX_ITEMS_PER_WORKER must be between 1 and 50." >&2
  exit 2
fi

job_is_running() {
  local label="$1"
  launchctl print "gui/${UID_VALUE}/${label}" 2>/dev/null | grep -q 'state = running'
}

if job_is_running "com.oosu.ai-mot-corpus-expansion"; then
  echo "Skipping full-text enrichment: corpus expansion is running."
  exit 0
fi

if job_is_running "com.oosu.ai-mot-embedding-backfill"; then
  echo "Skipping full-text enrichment: embedding backfill is running."
  exit 0
fi

worker_pids=()
for (( worker_index = 1; worker_index <= REGULAR_WORKER_COUNT; worker_index++ )); do
  source_lane="any"
  if (( worker_index <= OA_WORKER_COUNT )); then
    source_lane="oa"
  fi
  "$PYTHON" "$TIMEOUT" --timeout-seconds "$WORKER_TIMEOUT_SECONDS" -- \
    "$CLI" enrich-full-text \
    --max-items "$MAX_ITEMS_PER_WORKER" \
    --max-pdf-bytes 30000000 \
    --lease-minutes 15 \
    --source-lane "$source_lane" \
    --worker-id "regular:${HOST:-local}:$$:${worker_index}" &
  worker_pids+=("$!")
done

export SCIHUB_CLI_EXECUTABLE="${SCIHUB_CLI_EXECUTABLE:-$TOOLS_DIR/bin/scihub-cli}"
export LIBGEN_CLI_EXECUTABLE="${LIBGEN_CLI_EXECUTABLE:-$TOOLS_DIR/bin/libgen-cli}"

for (( worker_index = 1; worker_index <= DIRECT_WORKER_COUNT; worker_index++ )); do
  "$PYTHON" "$TIMEOUT" --timeout-seconds "$WORKER_TIMEOUT_SECONDS" -- \
    "$CLI" enrich-full-text-booster \
    --direct \
    --max-items "$MAX_ITEMS_PER_WORKER" \
    --max-pdf-bytes 30000000 \
    --lease-minutes 15 \
    --cooldown-hours 24 \
    --worker-id "direct:${HOST:-local}:$$:${worker_index}" &
  worker_pids+=("$!")
done

overall_status=0
for worker_pid in "${worker_pids[@]}"; do
  wait "$worker_pid" || overall_status=$?
done

exit "$overall_status"
