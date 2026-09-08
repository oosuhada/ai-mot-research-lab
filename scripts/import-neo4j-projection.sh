#!/bin/zsh
set -euo pipefail

ROOT="${1:?usage: import-neo4j-projection.sh <graph-runtime-root>}"
DOCKER="${DOCKER:-docker}"
IMAGE="${NEO4J_IMAGE:-neo4j:5.26-community}"

for file in \
  papers.csv authors.csv institutions.csv topics.csv \
  citations.csv paper_authors.csv author_institutions.csv paper_topics.csv; do
  [[ -s "$ROOT/import/$file" ]] || {
    echo "missing projection file: $ROOT/import/$file" >&2
    exit 2
  }
done

if [[ ! -d "$ROOT/data/databases/system" ]]; then
  "$DOCKER" compose -f "$ROOT/neo4j-prototype.compose.yml" up -d neo4j
  for _ in {1..90}; do
    health_status="$($DOCKER inspect --format '{{.State.Health.Status}}' ai-mot-neo4j-prototype 2>/dev/null || true)"
    [[ "$health_status" == "healthy" ]] && break
    sleep 2
  done
  [[ "$($DOCKER inspect --format '{{.State.Health.Status}}' ai-mot-neo4j-prototype)" == "healthy" ]]
fi

# Preserve the initialized system database/auth store, but replace only the
# derived `neo4j` read model with the latest PostgreSQL projection. Stopping an
# already-stopped container is harmless and also makes retry after a failed
# bulk import safe because we never boot the partial derived store first.
"$DOCKER" compose -f "$ROOT/neo4j-prototype.compose.yml" stop neo4j || true
"$DOCKER" run --rm \
  --user 7474:7474 \
  -v "$ROOT/data:/data" \
  -v "$ROOT/import:/var/lib/neo4j/import:ro" \
  "$IMAGE" \
  neo4j-admin database import full neo4j \
    --overwrite-destination=true \
    --multiline-fields=true \
    --nodes=Paper=/var/lib/neo4j/import/papers.csv \
    --nodes=Author=/var/lib/neo4j/import/authors.csv \
    --nodes=Institution=/var/lib/neo4j/import/institutions.csv \
    --nodes=Topic=/var/lib/neo4j/import/topics.csv \
    --relationships=CITES=/var/lib/neo4j/import/citations.csv \
    --relationships=AUTHORED=/var/lib/neo4j/import/paper_authors.csv \
    --relationships=AFFILIATED_WITH=/var/lib/neo4j/import/author_institutions.csv \
    --relationships=HAS_TOPIC=/var/lib/neo4j/import/paper_topics.csv

"$DOCKER" compose -f "$ROOT/neo4j-prototype.compose.yml" start neo4j
for _ in {1..90}; do
  health_status="$($DOCKER inspect --format '{{.State.Health.Status}}' ai-mot-neo4j-prototype 2>/dev/null || true)"
  [[ "$health_status" == "healthy" ]] && exit 0
  sleep 2
done
exit 3
