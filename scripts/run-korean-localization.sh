#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CLI="$ROOT_DIR/apps/api/.venv-prod/bin/research-lab"
UID_VALUE="$(id -u)"

job_is_running() {
  local label="$1"
  launchctl print "gui/${UID_VALUE}/${label}" 2>/dev/null | grep -q 'state = running'
}

for label in \
  "com.oosu.ai-mot-corpus-expansion" \
  "com.oosu.ai-mot-full-text-enrichment" \
  "com.oosu.ai-mot-embedding-backfill"; do
  if job_is_running "$label"; then
    echo "Skipping Korean localization: $label is running."
    exit 0
  fi
done

exec "$CLI" translate-localizations \
  --max-items 20 \
  --max-characters 15000 \
  --lookback-days 35
