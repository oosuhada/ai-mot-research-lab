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

acquire_lock() {
  if mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "$$" > "$LOCK_DIR/pid"
    return 0
  fi
  local owner=""
  if [[ -r "$LOCK_DIR/pid" ]]; then
    owner="$(<"$LOCK_DIR/pid")"
  fi
  if [[ "$owner" == <-> ]] && kill -0 "$owner" 2>/dev/null; then
    echo "Full-text queue maintenance is already running under PID $owner; no-op."
    return 1
  fi
  echo "Recovering stale full-text maintenance lock."
  rm -rf "$LOCK_DIR"
  mkdir "$LOCK_DIR"
  echo "$$" > "$LOCK_DIR/pid"
}

if ! acquire_lock; then
  exit 0
fi
trap 'rm -rf "$LOCK_DIR" 2>/dev/null || true' EXIT INT TERM

"$PYTHON" "$ROOT_DIR/scripts/prepare-private-blob-shards.py"

"$CLI" maintain-full-text-queue \
  --limit "${FULL_TEXT_MAINTENANCE_BATCH:-10000}" \
  --stale-grace-minutes 0 \
  --commit-every "${FULL_TEXT_MAINTENANCE_COMMIT_EVERY:-1000}"

