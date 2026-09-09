#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
API_SRC = ROOT / "apps/api/src"
sys.path.insert(0, str(API_SRC))

from research_lab.db import SessionLocal  # noqa: E402


def _parse_timestamp(value: object | None) -> datetime:
    if not isinstance(value, str) or not value:
        return datetime.now(UTC)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _load_feature_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            paper_id = str(payload.get("paper_id") or "").strip()
            if not paper_id:
                raise ValueError(f"Missing paper_id at {path}:{line_number}")
            rows.append(
                {
                    "paper_id": paper_id,
                    "citation_pagerank": float(payload.get("citation_pagerank") or payload.get("page_rank") or 0.0),
                    "citation_community": payload.get("citation_community") or payload.get("community"),
                    "source_projection_id": str(payload.get("source_projection_id") or "neo4j-prototype"),
                    "computed_at": _parse_timestamp(payload.get("computed_at")),
                }
            )
    return rows


def upsert_features(feature_path: Path | None) -> int:
    if feature_path is None:
        return 0
    rows = _load_feature_rows(feature_path)
    if not rows:
        return 0
    with SessionLocal() as session:
        session.execute(
            text(
                """
                INSERT INTO paper_graph_features (
                    paper_id,
                    citation_pagerank,
                    citation_community,
                    source_projection_id,
                    computed_at,
                    updated_at
                )
                VALUES (
                    CAST(:paper_id AS uuid),
                    :citation_pagerank,
                    :citation_community,
                    :source_projection_id,
                    :computed_at,
                    now()
                )
                ON CONFLICT (paper_id) DO UPDATE SET
                    citation_pagerank = EXCLUDED.citation_pagerank,
                    citation_community = EXCLUDED.citation_community,
                    source_projection_id = EXCLUDED.source_projection_id,
                    computed_at = EXCLUDED.computed_at,
                    updated_at = now()
                """
            ),
            rows,
        )
        session.commit()
    return len(rows)


def ensure_default_features() -> int:
    with SessionLocal() as session:
        result = session.execute(
            text(
                """
                INSERT INTO paper_graph_features (paper_id, citation_pagerank, source_projection_id, computed_at)
                SELECT p.id, 0.0, 'postgres-canonical-citations', now()
                FROM papers p
                ON CONFLICT (paper_id) DO NOTHING
                """
            )
        )
        session.commit()
        return int(result.rowcount or 0)


def rebuild_citation_neighbors(*, top_k_per_seed: int) -> int:
    with SessionLocal() as session:
        session.execute(text("DELETE FROM paper_graph_neighbors WHERE relation = 'citation'"))
        result = session.execute(
            text(
                """
                WITH raw_edges AS (
                    SELECT citing_paper_id AS seed_paper_id, cited_paper_id AS neighbor_paper_id
                    FROM citations
                    WHERE cited_paper_id IS NOT NULL
                    UNION ALL
                    SELECT cited_paper_id AS seed_paper_id, citing_paper_id AS neighbor_paper_id
                    FROM citations
                    WHERE cited_paper_id IS NOT NULL
                ),
                directed_edges AS (
                    SELECT seed_paper_id, neighbor_paper_id, count(*) AS citation_paths
                    FROM raw_edges
                    WHERE seed_paper_id <> neighbor_paper_id
                    GROUP BY seed_paper_id, neighbor_paper_id
                ),
                scored AS (
                    SELECT
                        edge.seed_paper_id,
                        edge.neighbor_paper_id,
                        edge.citation_paths,
                        coalesce(feature.citation_pagerank, 0.0) AS page_rank,
                        row_number() OVER (
                            PARTITION BY edge.seed_paper_id
                            ORDER BY coalesce(feature.citation_pagerank, 0.0) DESC, edge.neighbor_paper_id
                        ) AS position
                    FROM directed_edges edge
                    LEFT JOIN paper_graph_features feature ON feature.paper_id = edge.neighbor_paper_id
                )
                INSERT INTO paper_graph_neighbors (
                    seed_paper_id,
                    neighbor_paper_id,
                    relation,
                    distance,
                    weight,
                    citation_paths,
                    source_projection_id,
                    computed_at,
                    updated_at
                )
                SELECT
                    seed_paper_id,
                    neighbor_paper_id,
                    'citation',
                    citation_paths,
                    0.70 + least(0.25, ln(1 + greatest(page_rank, 0.0)) / 16.0),
                    1,
                    'postgres-canonical-citations',
                    now(),
                    now()
                FROM scored
                WHERE position <= :top_k_per_seed
                ON CONFLICT (seed_paper_id, neighbor_paper_id, relation) DO UPDATE SET
                    distance = EXCLUDED.distance,
                    weight = EXCLUDED.weight,
                    citation_paths = EXCLUDED.citation_paths,
                    source_projection_id = EXCLUDED.source_projection_id,
                    computed_at = EXCLUDED.computed_at,
                    updated_at = now()
                """
            ),
            {"top_k_per_seed": top_k_per_seed},
        )
        session.commit()
        return int(result.rowcount or 0)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Refresh compact PostgreSQL graph features and citation neighbors."
    )
    parser.add_argument("--features-jsonl", type=Path)
    parser.add_argument("--top-k-per-seed", type=int, default=80)
    parser.add_argument("--skip-citation-neighbors", action="store_true")
    args = parser.parse_args()
    if args.top_k_per_seed < 1 or args.top_k_per_seed > 500:
        raise SystemExit("--top-k-per-seed must be between 1 and 500")

    imported_features = upsert_features(args.features_jsonl)
    default_features = ensure_default_features()
    citation_neighbors = 0
    if not args.skip_citation_neighbors:
        citation_neighbors = rebuild_citation_neighbors(top_k_per_seed=args.top_k_per_seed)
    print(
        json.dumps(
            {
                "features_imported": imported_features,
                "default_features_inserted": default_features,
                "citation_neighbors_rebuilt": citation_neighbors,
                "top_k_per_seed": args.top_k_per_seed,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
