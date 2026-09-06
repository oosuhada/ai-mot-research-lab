#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
META_DONE="/Volumes/T9 SSD/server-data/ai-mot-research-lab/opencitations/meta-2026-06.completed"
INDEX_DONE="/Volumes/T9 SSD/server-data/ai-mot-research-lab/opencitations-index/v7/index-v7.completed"

while [[ ! -f "$META_DONE" ]]; do
  sleep 300
done

if [[ -f "$INDEX_DONE" ]]; then
  print "OpenCitations Index v7 already completed"
  exit 0
fi

exec "$ROOT_DIR/apps/api/.venv-prod/bin/python" "$ROOT_DIR/scripts/run-opencitations-index-pipeline.py"
