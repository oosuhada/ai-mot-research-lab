#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DATA_ROOT="/Volumes/T9 SSD/server-data/ai-mot-research-lab/opencitations"
ARCHIVE="$DATA_ROOT/output_csv_2026_06.7z"
EXTRACTED="$DATA_ROOT/meta-2026-06"
EXTRACT_TMP="$DATA_ROOT/meta-2026-06.tmp"
STATE="$DATA_ROOT/meta-2026-06-state.json"
DONE="$DATA_ROOT/meta-2026-06.completed"
URL="https://zenodo.org/api/records/20965426/files/output_csv_2026_06.7z/content"
EXPECTED_BYTES=8367870172
SEVENZIP="/opt/homebrew/bin/7zz"

mkdir -p "$DATA_ROOT"

if [[ -f "$DONE" ]]; then
  print "OpenCitations Meta June 2026 bootstrap already completed: $DONE"
  exit 0
fi

"$ROOT_DIR/apps/api/.venv-prod/bin/python" "$ROOT_DIR/scripts/check-private-storage.py"

current_size=0
if [[ -f "$ARCHIVE" ]]; then
  current_size=$(stat -f '%z' "$ARCHIVE")
fi

if (( current_size < EXPECTED_BYTES )); then
  print "Resuming OpenCitations Meta archive: ${current_size}/${EXPECTED_BYTES} bytes"
  /usr/bin/curl -L --fail --retry 12 --retry-delay 10 -C - -o "$ARCHIVE" "$URL"
fi

current_size=$(stat -f '%z' "$ARCHIVE")
if (( current_size != EXPECTED_BYTES )); then
  print -u2 "OpenCitations archive size mismatch: ${current_size}/${EXPECTED_BYTES}"
  exit 75
fi

if [[ ! -x "$SEVENZIP" ]]; then
  print -u2 "sevenzip is missing: $SEVENZIP"
  exit 69
fi

print "Testing OpenCitations archive integrity"
"$SEVENZIP" t "$ARCHIVE" >/dev/null

csv_count=0
if [[ -d "$EXTRACTED" ]]; then
  csv_count=$(find "$EXTRACTED" -type f -name '*.csv' | wc -l | tr -d ' ')
fi

if (( csv_count == 0 )); then
  rm -rf "$EXTRACT_TMP"
  mkdir -p "$EXTRACT_TMP"
  print "Extracting OpenCitations Meta archive"
  "$SEVENZIP" x -y -o"$EXTRACT_TMP" "$ARCHIVE"
  csv_count=$(find "$EXTRACT_TMP" -type f -name '*.csv' | wc -l | tr -d ' ')
  if (( csv_count == 0 )); then
    print -u2 "No CSV files found after OpenCitations extraction"
    exit 65
  fi
  rm -rf "$EXTRACTED"
  mv "$EXTRACT_TMP" "$EXTRACTED"
fi

print "Importing OpenCitations Meta CSV files: $csv_count"
"$ROOT_DIR/scripts/run-opencitations-meta-bootstrap.sh"

finished_at=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
printf 'completed_at=%s\narchive=%s\nstate=%s\n' "$finished_at" "$ARCHIVE" "$STATE" > "$DONE"

# The compressed source archive is retained for reproducibility.  The 56GB
# extracted working copy is disposable once the import has committed.
rm -rf "$EXTRACTED"
print "OpenCitations Meta bootstrap completed at $finished_at"
