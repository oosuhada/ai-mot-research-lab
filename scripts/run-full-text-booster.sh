#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CLI="$ROOT_DIR/apps/api/.venv-prod/bin/research-lab"
TOOLS_DIR="${FULL_TEXT_BOOSTER_TOOLS_DIR:-$HOME/.local/share/ai-mot-research-lab/full-text-booster-tools}"
UID_VALUE="$(id -u)"

export SCIHUB_CLI_EXECUTABLE="${SCIHUB_CLI_EXECUTABLE:-$TOOLS_DIR/bin/scihub-cli}"
export LIBGEN_CLI_EXECUTABLE="${LIBGEN_CLI_EXECUTABLE:-$TOOLS_DIR/bin/libgen-cli}"

if [[ ! -x "$SCIHUB_CLI_EXECUTABLE" ]]; then
  echo "Missing booster tool: $SCIHUB_CLI_EXECUTABLE" >&2
  exit 2
fi

if [[ ! -x "$LIBGEN_CLI_EXECUTABLE" ]]; then
  echo "Missing booster tool: $LIBGEN_CLI_EXECUTABLE" >&2
  exit 2
fi

job_is_running() {
  local label="$1"
  launchctl print "gui/${UID_VALUE}/${label}" 2>/dev/null | grep -q 'state = running'
}

if job_is_running "com.oosu.ai-mot-corpus-expansion"; then
  echo "Skipping full-text booster: corpus expansion is running."
  exit 0
fi

if job_is_running "com.oosu.ai-mot-embedding-backfill"; then
  echo "Skipping full-text booster: embedding backfill is running."
  exit 0
fi

exec "$CLI" enrich-full-text-booster \
  --direct \
  --max-items "${FULL_TEXT_DIRECT_MAX_ITEMS:-3}" \
  --max-pdf-bytes 30000000 \
  --lease-minutes 20 \
  --min-attempts 1 \
  --cooldown-hours 24 \
  --provider-timeout-seconds "${FULL_TEXT_DIRECT_PROVIDER_TIMEOUT_SECONDS:-20}" \
  --no-libgen-fallback
