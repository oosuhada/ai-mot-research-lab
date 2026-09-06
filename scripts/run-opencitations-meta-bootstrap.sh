#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
API_DIR="$ROOT_DIR/apps/api"
PYTHON="$API_DIR/.venv-prod/bin/python"
DATA_ROOT="/Volumes/T9 SSD/server-data/ai-mot-research-lab/opencitations"
EXTRACTED="$DATA_ROOT/meta-2026-06"
STATE="$DATA_ROOT/meta-2026-06-state.json"

"$PYTHON" "$ROOT_DIR/scripts/check-private-storage.py"

if [[ ! -d "$EXTRACTED" ]]; then
  print -u2 "OpenCitations extracted CSV directory missing: $EXTRACTED"
  exit 66
fi

cd "$API_DIR"
exec "$PYTHON" -m research_lab.cli import-opencitations-meta \
  --input "$EXTRACTED" \
  --from-year 2017 \
  --to-year 2027 \
  --max-new 100000 \
  --commit-every 2000 \
  --state "$STATE"
