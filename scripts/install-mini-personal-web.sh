#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
WEB_DIR="$ROOT_DIR/apps/web"
NODE_BIN="/opt/homebrew/opt/node@22/bin/node"
NEXT_BIN="$WEB_DIR/node_modules/next/dist/bin/next"
LABEL="com.oosu.ai-mot-research-web-personal"
PORT="${AI_MOT_PERSONAL_WEB_PORT:-8261}"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
TAILSCALE_IP="${AI_MOT_PERSONAL_WEB_HOST:-}"

if [[ -z "$TAILSCALE_IP" ]]; then
  if command -v tailscale >/dev/null 2>&1; then
    TAILSCALE_IP="$(tailscale ip -4 | head -n 1)"
  elif [[ -x /Applications/Tailscale.app/Contents/MacOS/Tailscale ]]; then
    TAILSCALE_IP="$(/Applications/Tailscale.app/Contents/MacOS/Tailscale ip -4 | head -n 1)"
  fi
fi

if [[ -z "$TAILSCALE_IP" ]]; then
  echo "Personal web install requires a Tailscale IPv4 address." >&2
  exit 1
fi

if [[ ! -x "$NODE_BIN" || ! -f "$NEXT_BIN" ]]; then
  echo "Personal web install requires the production Node/Next runtime." >&2
  exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${NODE_BIN}</string>
    <string>${NEXT_BIN}</string>
    <string>start</string>
    <string>-p</string>
    <string>${PORT}</string>
    <string>-H</string>
    <string>${TAILSCALE_IP}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${WEB_DIR}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>INTERNAL_API_BASE_URL</key>
    <string>http://127.0.0.1:8160</string>
    <key>WORKSPACE_MODE</key>
    <string>personal</string>
    <key>NODE_ENV</key>
    <string>production</string>
    <key>NEXT_TELEMETRY_DISABLED</key>
    <string>1</string>
    <key>PATH</key>
    <string>/opt/homebrew/opt/node@22/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <dict>
    <key>SuccessfulExit</key>
    <false/>
  </dict>
  <key>ThrottleInterval</key>
  <integer>5</integer>
  <key>StandardOutPath</key>
  <string>${HOME}/Library/Logs/ai-mot-research-web-personal.out.log</string>
  <key>StandardErrorPath</key>
  <string>${HOME}/Library/Logs/ai-mot-research-web-personal.err.log</string>
</dict>
</plist>
PLIST

plutil -lint "$PLIST"
launchctl bootout "gui/$(id -u)/${LABEL}" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl kickstart -k "gui/$(id -u)/${LABEL}"

echo "personal_web_host=${TAILSCALE_IP}"
echo "personal_web_port=${PORT}"
echo "personal_web_url=http://${TAILSCALE_IP}:${PORT}"
