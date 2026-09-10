#!/bin/zsh
set -euo pipefail

UID_VALUE="$(id -u)"

# Keep the Mac mini focused on the canonical PostgreSQL/API/graph-serving role.
# Fetching, PDF/XML parsing, and high-volume full-text queue consumption should
# run on Pro/Air workers so Mini keeps low latency for DB and API clients.
FULL_TEXT_LABELS=(
  com.oosu.ai-mot-full-text-enrichment
  com.oosu.ai-mot-full-text-bulk-oa
  com.oosu.ai-mot-full-text-booster
  com.oosu.ai-mot-full-text-paper-search-mcp
  com.oosu.ai-mot-semantic-scholar-oa-refresh
)

for label in "${FULL_TEXT_LABELS[@]}"; do
  launchctl bootout "gui/${UID_VALUE}/${label}" >/dev/null 2>&1 || true
  launchctl disable "gui/${UID_VALUE}/${label}" >/dev/null 2>&1 || true
  echo "{\"event\":\"mini_worker_disabled\",\"label\":\"${label}\"}"
done

echo '{"status":"completed","mode":"mini_db_primary"}'
