#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CLI="$ROOT_DIR/apps/api/.venv-prod/bin/research-lab"
UID_VALUE="$(id -u)"
WORKER_COUNT="${FULL_TEXT_ENRICHMENT_WORKERS:-3}"
MAX_ITEMS_PER_WORKER="${FULL_TEXT_ENRICHMENT_MAX_ITEMS_PER_WORKER:-10}"

case "$WORKER_COUNT" in
  1|2|3|4) ;;
  *)
    echo "FULL_TEXT_ENRICHMENT_WORKERS must be between 1 and 4." >&2
    exit 2
    ;;
esac

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
for worker_index in {1..$WORKER_COUNT}; do
  "$CLI" enrich-full-text \
    --max-items "$MAX_ITEMS_PER_WORKER" \
    --max-pdf-bytes 30000000 \
    --lease-minutes 20 &
  worker_pids+=("$!")
done

overall_status=0
for worker_pid in "${worker_pids[@]}"; do
  wait "$worker_pid" || overall_status=$?
done

exit "$overall_status"
