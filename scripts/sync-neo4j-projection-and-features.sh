#!/bin/zsh
set -euo pipefail

# Orchestrate the derived graph read model without making production serve
# requests from the MacBook Pro. Run this on the Mac mini.

REPO_DIR=${REPO_DIR:-$HOME/Services/ai-mot-research-lab}
PRO_HOST=${PRO_HOST:-gabriel@100.102.202.93}
PRO_GRAPH_DIR=${PRO_GRAPH_DIR:-/Users/gabriel/Services/ai-mot-research-graph-prototype}
WORK_ROOT=${WORK_ROOT:-$REPO_DIR/artifacts/graph-sync}
PYTHON=${PYTHON:-$REPO_DIR/apps/api/.venv-prod/bin/python}
LOCK_DIR=${LOCK_DIR:-/tmp/ai-mot-neo4j-projection-sync.lock}
SSH_IDENTITY=${SSH_IDENTITY:-$HOME/.ssh/id_ed25519_ai_mot_graph_sync}
SSH_BASE=(ssh -o BatchMode=yes -o ConnectTimeout=20 -i "$SSH_IDENTITY")
SCP_BASE=(scp -o BatchMode=yes -o ConnectTimeout=20 -i "$SSH_IDENTITY")
RSYNC_RSH="ssh -o BatchMode=yes -o ConnectTimeout=20 -i $SSH_IDENTITY"

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo '{"status":"skipped","reason":"lock_exists"}'
  exit 0
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

timestamp=$(date -u +%Y%m%dT%H%M%SZ)
run_dir="$WORK_ROOT/$timestamp"
projection_dir="$run_dir/projection"
feature_jsonl="$run_dir/neo4j-features.jsonl"
mkdir -p "$projection_dir" "$run_dir"

cd "$REPO_DIR"

echo "{\"event\":\"projection_export_start\",\"run_dir\":\"$run_dir\"}"
"$PYTHON" scripts/export-neo4j-projection.py --output "$projection_dir"

echo "{\"event\":\"projection_transfer_start\",\"host\":\"$PRO_HOST\"}"
rsync -e "$RSYNC_RSH" -az --delete "$projection_dir/" "$PRO_HOST:$PRO_GRAPH_DIR/import/"
"${SCP_BASE[@]}" scripts/load-neo4j-projection.cypher \
  scripts/materialize-neo4j-graph-analytics.cypher \
  scripts/export-neo4j-graph-features.py \
  "$PRO_HOST:/tmp/"

echo "{\"event\":\"neo4j_load_start\",\"host\":\"$PRO_HOST\"}"
"${SSH_BASE[@]}" "$PRO_HOST" "PRO_GRAPH_DIR='$PRO_GRAPH_DIR' /bin/zsh -s" <<'REMOTE'
set -euo pipefail
cd "$PRO_GRAPH_DIR"
docker_bin=/Applications/Docker.app/Contents/Resources/bin/docker
if [[ ! -x "$docker_bin" ]]; then
  docker_bin=/usr/local/bin/docker
fi
container=ai-mot-neo4j-prototype
auth_value=$(grep '^NEO4J_AUTH=' neo4j.env | sed 's/^NEO4J_AUTH=//')
neo4j_user=${auth_value%%/*}
neo4j_password=${auth_value#*/}
"$docker_bin" exec -i "$container" /var/lib/neo4j/bin/cypher-shell \
  -u "$neo4j_user" -p "$neo4j_password" < /tmp/load-neo4j-projection.cypher
"$docker_bin" exec -i "$container" /var/lib/neo4j/bin/cypher-shell \
  -u "$neo4j_user" -p "$neo4j_password" < /tmp/materialize-neo4j-graph-analytics.cypher
NEO4J_PASSWORD="$neo4j_password" /opt/homebrew/bin/python3 /tmp/export-neo4j-graph-features.py \
  --output /tmp/ai-mot-neo4j-features-sync.jsonl \
  --source-projection-id neo4j-prototype-sync
REMOTE

echo "{\"event\":\"feature_transfer_start\",\"host\":\"$PRO_HOST\"}"
"${SCP_BASE[@]}" "$PRO_HOST:/tmp/ai-mot-neo4j-features-sync.jsonl" "$feature_jsonl"

echo "{\"event\":\"postgres_refresh_start\"}"
"$PYTHON" scripts/refresh-postgres-graph-features.py --features-jsonl "$feature_jsonl"

ln -sfn "$run_dir" "$WORK_ROOT/latest"
echo "{\"status\":\"completed\",\"run_dir\":\"$run_dir\"}"
