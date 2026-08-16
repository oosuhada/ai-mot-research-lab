#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOCAL_CLI="$ROOT_DIR/apps/api/.venv/bin/research-lab"
SSH_HOST="${AI_MOT_SSH_HOST:-mac-mini}"
REMOTE_ROOT="${AI_MOT_REMOTE_ROOT:-/Users/gabrieljang/Services/ai-mot-research-lab}"
PROJECT_ID="${GEMINI_VERTEX_PROJECT:?Set GEMINI_VERTEX_PROJECT to the billed Vertex AI project id}"
MODEL="${GEMINI_VERTEX_MODEL:-gemini-3.7-flash}"
LOCATION="${GEMINI_VERTEX_LOCATION:-global}"
BUDGET_USD="${GEMINI_BOOTSTRAP_BUDGET_USD:-40}"
BATCH_SIZE="${GEMINI_BOOTSTRAP_BATCH_SIZE:-8}"
WORKERS="${GEMINI_BOOTSTRAP_WORKERS:-8}"

ARTIFACT_DIR="$ROOT_DIR/artifacts/gemini-localization"
mkdir -p "$ARTIFACT_DIR"
QUEUE_PATH="$ARTIFACT_DIR/bootstrap-queue.json"
OUTPUT_PATH="$ARTIFACT_DIR/bootstrap-ko.json"
LEDGER_PATH="$ARTIFACT_DIR/ledger.json"
REMOTE_QUEUE="/tmp/ai-mot-bootstrap-translation-queue.json"
REMOTE_OUTPUT="/tmp/ai-mot-bootstrap-translation-output.json"

cleanup() {
  ssh "$SSH_HOST" "rm -f '$REMOTE_QUEUE' '$REMOTE_OUTPUT'" >/dev/null 2>&1 || true
}
trap cleanup EXIT

ssh "$SSH_HOST" \
  "cd '$REMOTE_ROOT' && apps/api/.venv-prod/bin/research-lab export-translation-queue --locale ko --limit 100000 --output '$REMOTE_QUEUE'"
scp -q "$SSH_HOST:$REMOTE_QUEUE" "$QUEUE_PATH"

RECORDS="$(python3 - "$QUEUE_PATH" <<'PY'
import json, sys
print(len(json.load(open(sys.argv[1], encoding="utf-8"))))
PY
)"
if [[ "$RECORDS" == "0" ]]; then
  echo "No untranslated Korean localization records remain."
  exit 0
fi

"$LOCAL_CLI" translate-localization-export-gemini \
  --input "$QUEUE_PATH" \
  --output "$OUTPUT_PATH" \
  --ledger "$LEDGER_PATH" \
  --project "$PROJECT_ID" \
  --location "$LOCATION" \
  --model "$MODEL" \
  --budget-usd "$BUDGET_USD" \
  --batch-size "$BATCH_SIZE" \
  --workers "$WORKERS"

TRANSLATED="$(python3 - "$OUTPUT_PATH" <<'PY'
import json, sys
print(len(json.load(open(sys.argv[1], encoding="utf-8"))))
PY
)"
if [[ "$TRANSLATED" == "0" ]]; then
  echo "Gemini bootstrap produced no importable localizations; leaving DeepL steady-state fallback unchanged."
  exit 0
fi

scp -q "$OUTPUT_PATH" "$SSH_HOST:$REMOTE_OUTPUT"
ssh "$SSH_HOST" \
  "cd '$REMOTE_ROOT' && apps/api/.venv-prod/bin/research-lab import-localizations --input '$REMOTE_OUTPUT'"

echo "Gemini bootstrap imported $TRANSLATED Korean localizations."
