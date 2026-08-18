#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
API_DIR="$ROOT_DIR/apps/api"
CLI="$API_DIR/.venv-prod/bin/research-lab"
PYTHON="$API_DIR/.venv-prod/bin/python"
UID_VALUE="$(id -u)"

job_is_running() {
  local label="$1"
  launchctl print "gui/${UID_VALUE}/${label}" 2>/dev/null | grep -q 'state = running'
}

if job_is_running "com.oosu.ai-mot-full-text-enrichment"; then
  echo "Skipping corpus expansion: full-text enrichment is running."
  exit 0
fi

if job_is_running "com.oosu.ai-mot-embedding-backfill"; then
  echo "Skipping corpus expansion: embedding backfill is running."
  exit 0
fi

cd "$API_DIR"

HAS_OPENALEX_KEY="$($PYTHON - <<'PY'
from research_lab.config import get_settings

print("yes" if get_settings().openalex_api_key else "no")
PY
)"

if [[ "$HAS_OPENALEX_KEY" == "yes" ]]; then
  BULK_MAX_REQUESTS="${AI_MOT_BULK_MAX_REQUESTS:-50}"
  BULK_DAILY_REQUEST_CAP="${AI_MOT_BULK_DAILY_REQUEST_CAP:-480}"
  echo "Starting cursor-based corpus bulk bootstrap with max_requests=${BULK_MAX_REQUESTS}, daily_request_cap=${BULK_DAILY_REQUEST_CAP}; OpenAlex key configured=yes."
  exec "$CLI" bootstrap-corpus-bulk \
    --target-total 100000 \
    --from-year 2017 \
    --to-year 2026 \
    --max-requests "$BULK_MAX_REQUESTS" \
    --daily-request-cap "$BULK_DAILY_REQUEST_CAP"
fi

echo "OpenAlex key not configured; falling back to bounded basic-paging corpus expansion."
exec "$CLI" expand-corpus \
  --target-total 100000 \
  --from-year 2017 \
  --to-year 2026 \
  --max-pages 2
