#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CLI="$ROOT_DIR/apps/api/.venv-prod/bin/research-lab"
UID_VALUE="$(id -u)"

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

exec "$CLI" enrich-full-text \
  --max-items 10 \
  --max-pdf-bytes 30000000 \
  --lease-minutes 20
