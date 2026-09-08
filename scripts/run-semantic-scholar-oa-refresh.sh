#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CLI="$ROOT_DIR/apps/api/.venv-prod/bin/research-lab"
PYTHON="$ROOT_DIR/apps/api/.venv-prod/bin/python"
TIMEOUT="$ROOT_DIR/scripts/run-command-with-timeout.py"

if [[ ! -x "$CLI" ]]; then
  echo "Semantic Scholar OA refresh CLI is unavailable." >&2
  exit 2
fi

exec "$PYTHON" "$TIMEOUT" --timeout-seconds "${SEMANTIC_SCHOLAR_OA_REFRESH_TIMEOUT_SECONDS:-900}" -- \
  "$CLI" enrich-semantic-scholar-oa-batch \
  --max-items "${SEMANTIC_SCHOLAR_OA_REFRESH_MAX_ITEMS:-50000}" \
  --batch-size 500 \
  --refresh-days "${SEMANTIC_SCHOLAR_OA_REFRESH_DAYS:-30}"
