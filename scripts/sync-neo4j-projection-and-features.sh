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
MAX_ACTIVE_QUERIES=${GRAPH_SYNC_MAX_ACTIVE_QUERIES:-12}
MAX_PROCESSING_QUEUE_ITEMS=${GRAPH_SYNC_MAX_PROCESSING_QUEUE_ITEMS:-80}
SSH_BASE=(ssh -o BatchMode=yes -o ConnectTimeout=20 -i "$SSH_IDENTITY")
SCP_BASE=(scp -o BatchMode=yes -o ConnectTimeout=20 -i "$SSH_IDENTITY")
RSYNC_RSH="ssh -o BatchMode=yes -o ConnectTimeout=20 -i $SSH_IDENTITY"

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  if pgrep -f "sync-neo4j-projection-and-features.sh" >/dev/null 2>&1; then
    echo '{"status":"skipped","reason":"lock_exists"}'
    exit 0
  fi
  echo '{"event":"stale_lock_recovered","lock_dir":"'"$LOCK_DIR"'"}'
  rm -rf "$LOCK_DIR"
  mkdir "$LOCK_DIR"
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

timestamp=$(date -u +%Y%m%dT%H%M%SZ)
run_dir="$WORK_ROOT/$timestamp"
projection_dir="$run_dir/projection"
feature_jsonl="$run_dir/neo4j-features.jsonl"
mkdir -p "$projection_dir" "$run_dir"

cd "$REPO_DIR"

if ! "$PYTHON" - <<PY
import os
import sys

from sqlalchemy import create_engine, text

from research_lab.config import Settings

max_active_queries = int(os.environ.get("GRAPH_SYNC_MAX_ACTIVE_QUERIES", "$MAX_ACTIVE_QUERIES"))
max_processing_queue_items = int(os.environ.get("GRAPH_SYNC_MAX_PROCESSING_QUEUE_ITEMS", "$MAX_PROCESSING_QUEUE_ITEMS"))

try:
    settings = Settings()
    engine = create_engine(
        str(settings.database_url),
        connect_args={"connect_timeout": 5},
        pool_pre_ping=True,
    )
    with engine.connect() as conn:
        conn.execute(text("SET statement_timeout = 5000"))
        active_queries = int(
            conn.scalar(
                text(
                    """
                    SELECT count(*)
                    FROM pg_stat_activity
                    WHERE state = 'active'
                      AND pid <> pg_backend_pid()
                    """
                )
            )
            or 0
        )
        processing_queue_items = int(
            conn.scalar(text("SELECT count(*) FROM full_text_queue WHERE status = 'processing'")) or 0
        )
except Exception as exc:
    print(f'{{"status":"skipped","reason":"database_unavailable","error_type":"{type(exc).__name__}"}}')
    sys.exit(75)

print(
    '{'
    f'"event":"database_backpressure_check",'
    f'"active_queries":{active_queries},'
    f'"max_active_queries":{max_active_queries},'
    f'"processing_queue_items":{processing_queue_items},'
    f'"max_processing_queue_items":{max_processing_queue_items}'
    '}'
)
if active_queries > max_active_queries or processing_queue_items > max_processing_queue_items:
    print('{"status":"skipped","reason":"database_backpressure"}')
    sys.exit(75)
PY
then
  exit 0
fi

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
