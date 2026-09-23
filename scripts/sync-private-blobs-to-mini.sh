#!/bin/zsh
set -euo pipefail

LOCAL_ROOT="${PRIVATE_DATA_ROOT:-$HOME/Library/Caches/oosu-ai-mot-research-lab/private}"
REMOTE_HOST="${AI_MOT_PRIVATE_SYNC_HOST:-mac-mini}"
REMOTE_ROOT="${AI_MOT_PRIVATE_SYNC_ROOT:-ai-mot-private}"
REMOVE_SOURCE_FILES="${AI_MOT_PRIVATE_SYNC_REMOVE_SOURCE_FILES:-false}"
MIN_FREE_GB="${AI_MOT_PRIVATE_SYNC_MIN_FREE_GB:-100}"

if [[ ! -d "$LOCAL_ROOT" ]]; then
  echo "{\"status\":\"skipped\",\"reason\":\"local_private_root_missing\",\"path\":\"$LOCAL_ROOT\"}"
  exit 0
fi

if ! command -v rsync >/dev/null 2>&1 || ! command -v ssh >/dev/null 2>&1; then
  echo '{"status":"failed","reason":"rsync_or_ssh_missing"}' >&2
  exit 75
fi

remote_free_kb="$(ssh "$REMOTE_HOST" "set -e; test -d '$REMOTE_ROOT'; df -Pk '$REMOTE_ROOT'" | awk 'END {print $4}')"
if [[ ! "$remote_free_kb" =~ '^[0-9]+$' ]]; then
  echo '{"status":"failed","reason":"remote_free_space_unreadable"}' >&2
  exit 75
fi

minimum_free_kb=$(( MIN_FREE_GB * 1024 * 1024 ))
if (( remote_free_kb < minimum_free_kb )); then
  echo "{\"status\":\"failed\",\"reason\":\"remote_free_space_below_reserve\",\"free_kb\":${remote_free_kb},\"minimum_kb\":${minimum_free_kb}}" >&2
  exit 75
fi

rsync_args=(-rlt --size-only --partial)
if [[ "$REMOVE_SOURCE_FILES" == "true" ]]; then
  rsync_args+=(--remove-source-files)
fi

echo "{\"event\":\"private_blob_sync_started\",\"host\":\"${REMOTE_HOST}\",\"remote_root\":\"${REMOTE_ROOT}\",\"remove_source_files\":${REMOVE_SOURCE_FILES}}"
rsync "${rsync_args[@]}" "$LOCAL_ROOT/" "$REMOTE_HOST:$REMOTE_ROOT/"

if [[ "$REMOVE_SOURCE_FILES" == "true" ]]; then
  find "$LOCAL_ROOT" -depth -type d -empty -delete 2>/dev/null || true
  mkdir -p "$LOCAL_ROOT"
fi

echo '{"status":"completed","operation":"private_blob_sync"}'
