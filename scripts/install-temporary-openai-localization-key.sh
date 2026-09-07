#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SECRET_DIR="$HOME/Library/Application Support/oosu-research-secrets"
SECRET_FILE="$SECRET_DIR/openai-localization.key"
LABEL="com.oosu.ai-mot-openai-localization-window"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
TODAY_KST_NUM="$(TZ=Asia/Seoul date +%Y%m%d)"

if (( 10#$TODAY_KST_NUM < 20260907 || 10#$TODAY_KST_NUM > 20260910 )); then
  echo "Temporary OpenAI localization key installation is allowed only from 2026-09-07 through 2026-09-10 KST." >&2
  exit 2
fi

mkdir -p "$SECRET_DIR"
chmod 700 "$SECRET_DIR"
umask 077

read -rs "OPENAI_KEY?Paste the temporary OpenAI API key, then press Enter: "
echo
OPENAI_KEY="${OPENAI_KEY//$'\r'/}"
OPENAI_KEY="${OPENAI_KEY//$'\n'/}"
if [[ -z "$OPENAI_KEY" || "$OPENAI_KEY" != sk-* ]]; then
  unset OPENAI_KEY
  echo "The supplied value does not look like an OpenAI API key; nothing was written." >&2
  exit 2
fi

printf '%s\n' "$OPENAI_KEY" > "$SECRET_FILE"
unset OPENAI_KEY
chmod 600 "$SECRET_FILE"

UID_VALUE="$(id -u)"
if ! launchctl print "gui/${UID_VALUE}/${LABEL}" >/dev/null 2>&1; then
  if [[ ! -f "$PLIST" ]]; then
    cp "$ROOT_DIR/deploy/launchd/$LABEL.plist" "$PLIST"
  fi
  launchctl bootstrap "gui/${UID_VALUE}" "$PLIST"
fi
launchctl kickstart -k "gui/${UID_VALUE}/${LABEL}"

echo "Temporary OpenAI localization key installed with mode 600."
echo "The localization worker has been started; the key will be retired automatically after 2026-09-10 KST."
