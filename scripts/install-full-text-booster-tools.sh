#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$ROOT_DIR/apps/api/.venv-prod/bin/python"
TOOLS_DIR="${FULL_TEXT_BOOSTER_TOOLS_DIR:-$HOME/.local/share/ai-mot-research-lab/full-text-booster-tools}"

mkdir -p "$(dirname "$TOOLS_DIR")"
if [[ ! -x "$TOOLS_DIR/bin/python" ]]; then
  "$PYTHON" -m venv "$TOOLS_DIR"
fi

"$TOOLS_DIR/bin/python" -m pip install --disable-pip-version-check \
  scihub-cli==0.5.2 \
  libgen-downloader==0.0.104 \
  click==8.1.7

"$TOOLS_DIR/bin/scihub-cli" --help >/dev/null
"$TOOLS_DIR/bin/libgen-cli" --help >/dev/null
echo "Full-text booster tools are ready in $TOOLS_DIR"
