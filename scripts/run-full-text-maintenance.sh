#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CLI="$ROOT_DIR/apps/api/.venv-prod/bin/research-lab"
PYTHON="$ROOT_DIR/apps/api/.venv-prod/bin/python"
ARTIFACT_DIR="$ROOT_DIR/artifacts/full-text"
LOCK_DIR="$ARTIFACT_DIR/.maintenance-lock"

mkdir -p "$ARTIFACT_DIR"
if ! "$PYTHON" "$ROOT_DIR/scripts/check-private-storage.py"; then
  echo "Skipping full-text queue maintenance because private storage is unavailable." >&2
  exit 0
fi

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "Full-text queue maintenance is already running; no-op."
  exit 0
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT INT TERM

exec "$CLI" maintain-full-text-queue \
  --limit "${FULL_TEXT_MAINTENANCE_BATCH:-10000}" \
  --stale-grace-minutes 0 \
  --commit-every "${FULL_TEXT_MAINTENANCE_COMMIT_EVERY:-1000}"

