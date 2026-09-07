#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CLI="$ROOT_DIR/apps/api/.venv-prod/bin/research-lab"
PYTHON="$ROOT_DIR/apps/api/.venv-prod/bin/python"
TIMEOUT="$ROOT_DIR/scripts/run-command-with-timeout.py"

if ! "$PYTHON" "$ROOT_DIR/scripts/check-private-storage.py"; then
  echo "Skipping paper-search-mcp full-text lane because private storage is unavailable." >&2
  exit 0
fi

"$CLI" maintain-full-text-queue --limit "${FULL_TEXT_MAINTENANCE_BATCH:-5000}" --stale-grace-minutes 0

exec "$PYTHON" "$TIMEOUT" \
  --timeout-seconds "${FULL_TEXT_MCP_WORKER_TIMEOUT_SECONDS:-600}" -- \
  "$CLI" enrich-full-text-paper-search \
    --max-items "${FULL_TEXT_MCP_MAX_ITEMS:-5}" \
    --max-pdf-bytes 30000000 \
    --lease-minutes 15 \
    --min-prior-attempts 1 \
    --worker-id "paper-search-mcp:${HOST:-local}:$$"
