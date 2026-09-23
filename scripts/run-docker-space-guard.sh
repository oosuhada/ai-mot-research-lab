#!/bin/zsh
set -euo pipefail

ORBSTACK_BIN="${ORBSTACK_BIN:-$HOME/.orbstack/bin/orbctl}"
DOCKER_BIN="${DOCKER_BIN:-$HOME/.orbstack/bin/docker}"
DATA_MOUNT="${AI_MOT_SPACE_GUARD_MOUNT:-/System/Volumes/Data}"
MIN_FREE_GB="${AI_MOT_SPACE_GUARD_MIN_FREE_GB:-25}"
IMAGE_MAX_AGE="${AI_MOT_SPACE_GUARD_IMAGE_MAX_AGE:-168h}"
BUILD_MAX_AGE="${AI_MOT_SPACE_GUARD_BUILD_MAX_AGE:-72h}"

free_gb() {
  df -Pk "$DATA_MOUNT" | awk 'NR == 2 { printf "%d\n", $4 / 1024 / 1024 }'
}

before="$(free_gb)"
echo "{\"event\":\"space_guard_check\",\"free_gb\":$before,\"minimum_free_gb\":$MIN_FREE_GB}"

if (( before >= MIN_FREE_GB )); then
  echo '{"status":"completed","action":"none"}'
  exit 0
fi

# These are disposable package/build caches only. Never touch research blobs,
# PostgreSQL data, Docker volumes, or user documents here.
rm -rf +  "$HOME/.npm/_cacache" +  "$HOME/Library/Caches/Homebrew" +  "$HOME/Library/Caches/node-gyp" +  "$HOME/Library/Caches/pnpm" +  "$HOME/.cache/uv" +  "$HOME/.cache/node" +  2>/dev/null || true

if [[ -x "$ORBSTACK_BIN" ]] && [[ "$("$ORBSTACK_BIN" status 2>/dev/null || true)" != "Running" ]]; then
  "$ORBSTACK_BIN" start >/dev/null 2>&1 || true
  for _ in {1..30}; do
    [[ "$("$ORBSTACK_BIN" status 2>/dev/null || true)" == "Running" ]] && break
    sleep 1
  done
fi

if [[ -x "$DOCKER_BIN" ]] && "$DOCKER_BIN" info >/dev/null 2>&1; then
  "$DOCKER_BIN" container prune -f --filter "until=$IMAGE_MAX_AGE" >/dev/null || true
  "$DOCKER_BIN" image prune -a -f --filter "until=$IMAGE_MAX_AGE" >/dev/null || true
  "$DOCKER_BIN" builder prune -a -f --filter "until=$BUILD_MAX_AGE" >/dev/null || true
fi

after="$(free_gb)"
echo "{\"status\":\"completed\",\"action\":\"pruned_non_volume_docker_data\",\"free_gb_before\":$before,\"free_gb_after\":$after}"

if (( after < MIN_FREE_GB )); then
  echo "{\"warning\":\"free_space_still_below_threshold\",\"free_gb\":$after}" >&2
  exit 75
fi
