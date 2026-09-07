#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CLI="$ROOT_DIR/apps/api/.venv-prod/bin/research-lab"
UID_VALUE="$(id -u)"

TODAY_KST_NUM="$(TZ=Asia/Seoul date +%Y%m%d)"
if (( TODAY_KST_NUM >= 20260907 && TODAY_KST_NUM <= 20260910 )); then
  echo "Skipping DeepL localization during the temporary OpenAI burst window."
  exit 0
fi

job_is_running() {
  local label="$1"
  launchctl print "gui/${UID_VALUE}/${label}" 2>/dev/null | grep -q 'state = running'
}

for label in \
  "com.oosu.ai-mot-corpus-expansion" \
  "com.oosu.ai-mot-embedding-backfill"; do
  if job_is_running "$label"; then
    echo "Skipping Korean localization: $label is running."
    exit 0
  fi
done

exec "$CLI" translate-localizations \
  --max-items "${DEEPL_LOCALIZATION_MAX_ITEMS:-200}" \
  --max-characters "${DEEPL_LOCALIZATION_MAX_CHARACTERS:-50000}" \
  --lookback-days "${DEEPL_LOCALIZATION_LOOKBACK_DAYS:-3650}"
