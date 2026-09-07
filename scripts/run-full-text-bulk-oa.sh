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


job_is_running() {
  local label="$1"
  launchctl print "gui/${UID_VALUE}/${label}" 2>/dev/null | grep -q 'state = running'
}

if job_is_running "com.oosu.ai-mot-corpus-expansion" || job_is_running "com.oosu.ai-mot-embedding-backfill"; then
  echo "Skipping bulk OA full-text enrichment while a database-heavy maintenance job is running."
  exit 0
fi

"$CLI" maintain-full-text-queue \
  --limit "${FULL_TEXT_MAINTENANCE_BATCH:-5000}" \
  --stale-grace-minutes 0

"$PYTHON" "$TIMEOUT" --timeout-seconds "${FULL_TEXT_BULK_WORKER_TIMEOUT_SECONDS:-720}" -- \
  "$CLI" enrich-full-text-pmc-bulk \
  --max-items "${FULL_TEXT_PMC_BULK_MAX_ITEMS:-150}" \
  --download-workers "${FULL_TEXT_PMC_DOWNLOAD_WORKERS:-6}" \
  --max-xml-bytes 30000000 \
  --lease-minutes 15 \
  --worker-id "pmc-bulk:${HOST:-local}:$$" &
pmc_pid="$!"

"$PYTHON" "$TIMEOUT" --timeout-seconds "${FULL_TEXT_BULK_WORKER_TIMEOUT_SECONDS:-720}" -- \
  "$CLI" enrich-full-text \
  --source-lane arxiv \
  --max-items "${FULL_TEXT_ARXIV_LANE_MAX_ITEMS:-25}" \
  --max-pdf-bytes 30000000 \
  --lease-minutes 15 \
  --worker-id "arxiv-lane:${HOST:-local}:$$" &
arxiv_pid="$!"

overall_status=0
wait "$pmc_pid" || overall_status=$?
wait "$arxiv_pid" || overall_status=$?
exit "$overall_status"
