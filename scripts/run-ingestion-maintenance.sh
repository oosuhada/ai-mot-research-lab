#!/bin/zsh
set -euo pipefail

ROOT_DIR="${0:A:h:h}"
PYTHON="$ROOT_DIR/apps/api/.venv-prod/bin/python"

cd "$ROOT_DIR/apps/api"
exec "$PYTHON" -m research_lab.cli sweep-stale-ingestion-runs \
  --heartbeat-timeout-hours 6 \
  --no-heartbeat-timeout-hours 24
