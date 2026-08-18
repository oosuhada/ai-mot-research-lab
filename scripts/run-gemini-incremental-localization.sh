#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CLI="$ROOT_DIR/apps/api/.venv-prod/bin/research-lab"
UID_VALUE="$(id -u)"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export CLOUDSDK_PYTHON="${CLOUDSDK_PYTHON:-/opt/homebrew/bin/python3.14}"

PROJECT_ID="${GEMINI_VERTEX_PROJECT:-flai-oosuhada-20260506}"
MODEL="${GEMINI_VERTEX_MODEL:-gemini-3.7-flash}"
LOCATION="${GEMINI_VERTEX_LOCATION:-global}"
BUDGET_USD="${GEMINI_INCREMENTAL_BUDGET_USD:-15}"
MAX_ITEMS="${GEMINI_INCREMENTAL_MAX_ITEMS:-64}"
BATCH_SIZE="${GEMINI_INCREMENTAL_BATCH_SIZE:-8}"
WORKERS="${GEMINI_INCREMENTAL_WORKERS:-8}"
DURATION_SECONDS="${GEMINI_INCREMENTAL_DURATION_SECONDS:-604800}"

ARTIFACT_DIR="$ROOT_DIR/artifacts/gemini-localization"
WINDOW_PATH="$ARTIFACT_DIR/incremental-window.json"
QUEUE_PATH="$ARTIFACT_DIR/incremental-queue.json"
OUTPUT_PATH="$ARTIFACT_DIR/incremental-ko.json"
LEDGER_PATH="$ARTIFACT_DIR/ledger.json"

mkdir -p "$ARTIFACT_DIR"

if [[ ! -x "$CLI" ]]; then
  echo "Gemini incremental localization cannot start: CLI not found at $CLI" >&2
  exit 1
fi

if ! command -v gcloud >/dev/null 2>&1; then
  echo "Gemini incremental localization cannot start: gcloud is not installed or not on PATH." >&2
  exit 1
fi

if [[ ! -s "$LEDGER_PATH" ]]; then
  echo "Gemini incremental localization cannot start: existing budget ledger is missing at $LEDGER_PATH" >&2
  exit 1
fi

NOW_EPOCH="$(date +%s)"
if [[ ! -s "$WINDOW_PATH" ]]; then
  /usr/bin/python3 - "$WINDOW_PATH" "$NOW_EPOCH" "$DURATION_SECONDS" <<'PY'
import json
import sys
from datetime import datetime

path = sys.argv[1]
started_epoch = int(sys.argv[2])
duration_seconds = int(sys.argv[3])
expires_epoch = started_epoch + max(duration_seconds, 0)

def iso(epoch: int) -> str:
    return datetime.fromtimestamp(epoch).astimezone().isoformat()

with open(path, "w", encoding="utf-8") as handle:
    json.dump(
        {
            "started_epoch": started_epoch,
            "expires_epoch": expires_epoch,
            "started_at": iso(started_epoch),
            "expires_at": iso(expires_epoch),
        },
        handle,
        indent=2,
        ensure_ascii=False,
    )
PY
fi

EXPIRES_EPOCH="$(/usr/bin/python3 - "$WINDOW_PATH" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)
print(int(payload["expires_epoch"]))
PY
)"

if (( NOW_EPOCH >= EXPIRES_EPOCH )); then
  echo "Gemini incremental localization window expired; no-op."
  exit 0
fi

job_is_running() {
  local label="$1"
  launchctl print "gui/${UID_VALUE}/${label}" 2>/dev/null | grep -q 'state = running'
}

for label in \
  "com.oosu.ai-mot-corpus-expansion" \
  "com.oosu.ai-mot-full-text-enrichment" \
  "com.oosu.ai-mot-embedding-backfill" \
  "com.oosu.ai-mot-korean-localization"; do
  if job_is_running "$label"; then
    echo "Skipping Gemini incremental localization: $label is running."
    exit 0
  fi
done

rm -f "$QUEUE_PATH" "$OUTPUT_PATH"
"$CLI" export-translation-queue \
  --locale ko \
  --limit "$MAX_ITEMS" \
  --only-untranslated \
  --output "$QUEUE_PATH"

RECORDS="$(/usr/bin/python3 - "$QUEUE_PATH" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    print(len(json.load(handle)))
PY
)"

if [[ "$RECORDS" == "0" ]]; then
  echo "Gemini incremental localization queue is empty; no-op."
  exit 0
fi

echo "Gemini incremental localization: translating $RECORDS records."
"$CLI" translate-localization-export-gemini \
  --input "$QUEUE_PATH" \
  --output "$OUTPUT_PATH" \
  --ledger "$LEDGER_PATH" \
  --project "$PROJECT_ID" \
  --location "$LOCATION" \
  --model "$MODEL" \
  --budget-usd "$BUDGET_USD" \
  --batch-size "$BATCH_SIZE" \
  --workers "$WORKERS"

if [[ ! -s "$OUTPUT_PATH" ]]; then
  echo "Gemini incremental localization produced no output; budget may be exhausted."
  exit 0
fi

TRANSLATED="$(/usr/bin/python3 - "$OUTPUT_PATH" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    print(len(json.load(handle)))
PY
)"

if [[ "$TRANSLATED" == "0" ]]; then
  echo "Gemini incremental localization translated 0 records; no import required."
  exit 0
fi

"$CLI" import-localizations --input "$OUTPUT_PATH"
echo "Gemini incremental localization imported $TRANSLATED records."
