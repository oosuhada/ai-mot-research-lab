#!/bin/zsh
set -euo pipefail

ROOT_DIR="${AI_MOT_RESEARCH_ROOT:-$HOME/Services/ai-mot-research-lab}"
BROWSER_PYTHON="${SCOPUS_BROWSER_PYTHON:-$HOME/Services/research-browser-automation/.venv/bin/python}"

if [[ ! -x "$BROWSER_PYTHON" ]]; then
  echo "Scopus browser sync skipped: Playwright interpreter is unavailable: $BROWSER_PYTHON" >&2
  exit 75
fi

cd "$ROOT_DIR"

if ! "$ROOT_DIR/apps/api/.venv-prod/bin/python" "$ROOT_DIR/scripts/check-private-storage.py"; then
  echo "Scopus browser sync skipped: external storage is unavailable." >&2
  exit 75
fi

exec "$BROWSER_PYTHON" "$ROOT_DIR/scripts/scopus-browser-sync.py" \
  --repo "$ROOT_DIR" \
  --max-results-per-axis "${SCOPUS_BROWSER_MAX_RESULTS_PER_AXIS:-10}"
