#!/bin/sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_root"

output="$repo_root/artifacts/analytics/$(date -u +%F).duckdb"
exec apps/api/.venv-prod/bin/research-lab analytics-snapshot --output "$output"
