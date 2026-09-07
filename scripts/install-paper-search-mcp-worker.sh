#!/bin/zsh
set -euo pipefail

ROOT="${PAPER_SEARCH_MCP_HOME:-$HOME/.local/share/ai-mot-research-lab/paper-search-mcp}"
VENV="$ROOT/venv"
PYTHON_BIN="${PAPER_SEARCH_MCP_BOOTSTRAP_PYTHON:-/opt/homebrew/bin/python3}"
PINNED_REF="${PAPER_SEARCH_MCP_PINNED_REF:-234678a}"

mkdir -p "$ROOT"
if [[ ! -x "$VENV/bin/python" ]]; then
  "$PYTHON_BIN" -m venv "$VENV"
fi
"$VENV/bin/python" -m pip install --disable-pip-version-check --upgrade pip >/dev/null
"$VENV/bin/python" -m pip install --disable-pip-version-check \
  "git+https://github.com/openags/paper-search-mcp.git@${PINNED_REF}"

"$VENV/bin/paper-search" sources >/dev/null
echo "$VENV/bin/paper-search"
