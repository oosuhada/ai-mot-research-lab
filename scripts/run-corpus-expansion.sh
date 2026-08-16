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

MAX_PAGES="$($PYTHON - <<'PY'
from research_lab.config import get_settings

print(10 if get_settings().openalex_api_key else 2)
PY
)"

echo "Starting corpus expansion with max_pages=${MAX_PAGES}; OpenAlex key configured=$([[ "$MAX_PAGES" == "10" ]] && echo yes || echo no)."

exec "$CLI" expand-corpus \
  --target-total 100000 \
  --from-year 2017 \
  --to-year 2026 \
  --max-pages "$MAX_PAGES"
