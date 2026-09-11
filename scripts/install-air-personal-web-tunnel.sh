#!/bin/zsh
set -euo pipefail

LABEL="com.oosu.ai-mot-personal-web-tunnel"
PORT="${AI_MOT_PERSONAL_WEB_PORT:-8261}"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
SSH_BIN="/usr/bin/ssh"

if [[ ! -x "$SSH_BIN" ]]; then
  echo "ssh is required" >&2
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
    <string>${SSH_BIN}</string>
    <string>-N</string>
    <string>-T</string>
    <string>-o</string>
    <string>ExitOnForwardFailure=yes</string>
    <string>-o</string>
    <string>ServerAliveInterval=30</string>
    <string>-o</string>
    <string>ServerAliveCountMax=3</string>
    <string>-L</string>
    <string>127.0.0.1:${PORT}:127.0.0.1:${PORT}</string>
    <string>mac-mini</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ThrottleInterval</key>
  <integer>5</integer>
  <key>StandardOutPath</key>
  <string>${HOME}/Library/Logs/ai-mot-personal-web-tunnel.out.log</string>
  <key>StandardErrorPath</key>
  <string>${HOME}/Library/Logs/ai-mot-personal-web-tunnel.err.log</string>
</dict>
</plist>
PLIST

plutil -lint "$PLIST"
launchctl bootout "gui/$(id -u)/${LABEL}" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl kickstart -k "gui/$(id -u)/${LABEL}"

echo "personal_web_url=http://127.0.0.1:${PORT}"
