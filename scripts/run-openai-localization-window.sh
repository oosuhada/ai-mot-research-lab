#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CLI="$ROOT_DIR/apps/api/.venv-prod/bin/research-lab"
TIMEOUT_RUNNER="$ROOT_DIR/scripts/run-command-with-timeout.py"
ARTIFACT_DIR="$ROOT_DIR/artifacts/openai-localization"
SECRET_FILE="${OPENAI_LOCALIZATION_SECRET_FILE:-$HOME/Library/Application Support/oosu-research-secrets/openai-localization.key}"
QUEUE_PATH="$ARTIFACT_DIR/queue.json"
OUTPUT_PATH="$ARTIFACT_DIR/ko.json"
LEDGER_PATH="$ARTIFACT_DIR/ledger.json"
LOCK_DIR="$ARTIFACT_DIR/.lock"

MODEL="${OPENAI_LOCALIZATION_MODEL:-gpt-5.6-luna}"
MAX_ITEMS="${OPENAI_LOCALIZATION_MAX_ITEMS:-384}"
BATCH_SIZE="${OPENAI_LOCALIZATION_BATCH_SIZE:-8}"
WORKERS="${OPENAI_LOCALIZATION_WORKERS:-8}"
BUDGET_USD="${OPENAI_LOCALIZATION_BUDGET_USD:-200}"
TIMEOUT_SECONDS="${OPENAI_LOCALIZATION_TIMEOUT_SECONDS:-540}"

mkdir -p "$ARTIFACT_DIR"

TODAY_KST="$(TZ=Asia/Seoul date +%F)"
if [[ "$TODAY_KST" < "2026-09-07" ]]; then
  echo "OpenAI localization window has not started; no-op."
  exit 0
fi
if [[ "$TODAY_KST" > "2026-09-10" ]]; then
  # The supplied key was explicitly temporary. Remove the dedicated secret
  # file as soon as the four-day window is over so later jobs cannot reuse it.
  rm -f "$SECRET_FILE"
  if [[ -f "$ROOT_DIR/.env" ]]; then
    /usr/bin/python3 - "$ROOT_DIR/.env" <<'PY'
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
lines = path.read_text(encoding="utf-8").splitlines()
updated = []
for line in lines:
    if line.startswith("OPENAI_API_KEY="):
        updated.append("OPENAI_API_KEY=")
    else:
        updated.append(line)
path.write_text("\n".join(updated) + "\n", encoding="utf-8")
PY
  fi
  echo "OpenAI localization window ended on 2026-09-10 KST; key retired and job is a no-op."
  exit 0
fi

if [[ ! -x "$CLI" ]]; then
  echo "OpenAI localization cannot start: CLI not found at $CLI" >&2
  exit 1
fi
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "OpenAI localization already has an active run; no-op."
  exit 0
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT INT TERM

if [[ -r "$SECRET_FILE" ]]; then
  export OPENAI_API_KEY="$(<"$SECRET_FILE")"
elif ! grep -Eq '^OPENAI_API_KEY=.+$' "$ROOT_DIR/.env" 2>/dev/null; then
  echo "OpenAI localization is waiting for the temporary API key; no-op."
  exit 0
fi

rm -f "$QUEUE_PATH" "$OUTPUT_PATH"
"$CLI" export-translation-queue \
  --locale ko \
  --limit "$MAX_ITEMS" \
  --only-untranslated \
  --include-title-only \
  --output "$QUEUE_PATH"

RECORDS="$(/usr/bin/python3 - "$QUEUE_PATH" <<'PY'
import json
import sys
with open(sys.argv[1], encoding="utf-8") as handle:
    print(len(json.load(handle)))
PY
)"

if [[ "$RECORDS" == "0" ]]; then
  echo "OpenAI localization queue is empty; no-op."
  exit 0
fi

echo "OpenAI localization: translating $RECORDS records with $MODEL."
"$ROOT_DIR/apps/api/.venv-prod/bin/python" "$TIMEOUT_RUNNER" \
  --timeout-seconds "$TIMEOUT_SECONDS" -- \
  "$CLI" translate-localization-export-openai \
    --input "$QUEUE_PATH" \
    --output "$OUTPUT_PATH" \
    --ledger "$LEDGER_PATH" \
    --model "$MODEL" \
    --budget-usd "$BUDGET_USD" \
    --batch-size "$BATCH_SIZE" \
    --workers "$WORKERS"

if [[ ! -s "$OUTPUT_PATH" ]]; then
  echo "OpenAI localization produced no output; no import performed."
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
  echo "OpenAI localization translated 0 records; no import required."
  exit 0
fi

"$CLI" import-localizations --input "$OUTPUT_PATH"
echo "OpenAI localization imported $TRANSLATED records."

