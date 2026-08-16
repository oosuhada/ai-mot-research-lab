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
    echo "Skipping steady-state discovery: $label is running."
    exit 0
  fi
done

STATUS_JSON="$($CLI corpus-expansion-status)"
READY="$(python3 -c 'import json,sys; p=json.load(sys.stdin); print("yes" if int(p["corpus_count"]) >= int(p["target_total"]) else "no")' <<<"$STATUS_JSON")"
if [[ "$READY" != "yes" ]]; then
  echo "Skipping steady-state discovery: bootstrap corpus target has not been reached."
  exit 0
fi

"$CLI" discover-daily --lookback-days 3 --max-pages-per-axis 2
exec "$CLI" refresh-intelligence --discovery-days 2
