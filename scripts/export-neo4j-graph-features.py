#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _auth_header(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
    return f"Basic {token}"


def _post_cypher(
    *,
    uri: str,
    username: str,
    password: str,
    statement: str,
    parameters: dict[str, Any],
    timeout: float,
) -> list[dict[str, Any]]:
    body = json.dumps({"statements": [{"statement": statement, "parameters": parameters}]}).encode("utf-8")
    request = urllib.request.Request(
        f"{uri.rstrip('/')}/db/neo4j/tx/commit",
        data=body,
        headers={
            "Authorization": _auth_header(username, password),
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    errors = payload.get("errors") or []
    if errors:
        code = errors[0].get("code", "Neo4jError") if isinstance(errors[0], dict) else "Neo4jError"
        raise RuntimeError(f"Neo4j query failed: {code}")
    result = (payload.get("results") or [{}])[0]
    columns = result.get("columns") or []
    return [dict(zip(columns, item.get("row") or [], strict=False)) for item in result.get("data") or []]


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Neo4j paper PageRank/community features as JSONL.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--uri", default=os.environ.get("NEO4J_URI", "http://127.0.0.1:7474"))
    parser.add_argument("--username", default=os.environ.get("NEO4J_USERNAME", "neo4j"))
    parser.add_argument("--password", default=os.environ.get("NEO4J_PASSWORD"))
    parser.add_argument("--batch-size", type=int, default=5000)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--source-projection-id", default="neo4j-prototype")
    args = parser.parse_args()
    if not args.password:
        raise SystemExit("NEO4J_PASSWORD or --password is required")
    if args.batch_size < 100 or args.batch_size > 50_000:
        raise SystemExit("--batch-size must be between 100 and 50000")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    computed_at = datetime.now(UTC).isoformat()
    written = 0
    skip = 0
    with args.output.open("w", encoding="utf-8") as stream:
        while True:
            rows = _post_cypher(
                uri=args.uri,
                username=args.username,
                password=args.password,
                statement="""
                MATCH (paper:Paper)
                RETURN paper.paper_id AS paper_id,
                       coalesce(paper.citationPageRank, 0.0) AS citation_pagerank,
                       paper.citationCommunity AS citation_community
                ORDER BY paper.paper_id
                SKIP $skip
                LIMIT $limit
                """,
                parameters={"skip": skip, "limit": args.batch_size},
                timeout=args.timeout,
            )
            if not rows:
                break
            for row in rows:
                stream.write(
                    json.dumps(
                        {
                            "paper_id": row["paper_id"],
                            "citation_pagerank": row.get("citation_pagerank") or 0.0,
                            "citation_community": row.get("citation_community"),
                            "source_projection_id": args.source_projection_id,
                            "computed_at": computed_at,
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
            written += len(rows)
            skip += len(rows)
            print(json.dumps({"written": written}), file=sys.stderr)
    print(json.dumps({"output": str(args.output), "written": written}, sort_keys=True))


if __name__ == "__main__":
    main()
