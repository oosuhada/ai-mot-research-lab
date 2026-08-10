from __future__ import annotations

import argparse
import json
from typing import Any

from research_lab.config import get_settings
from research_lab.db import SessionLocal
from research_lab.ingestion.service import OpenAlexIngestionService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="research-lab")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest = subparsers.add_parser("ingest-openalex", help="Build or refresh the scoped OpenAlex seed corpus")
    ingest.add_argument("--target", type=int, default=600, help="Minimum design target for the seed corpus")
    ingest.add_argument("--from-year", type=int, default=2018, help="Default publication lower bound")

    subparsers.add_parser("evaluate", help="Run the committed small-set retrieval/evidence evaluation")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "ingest-openalex":
        result = run_openalex_ingestion(target=args.target, from_year=args.from_year)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    if args.command == "evaluate":
        from research_lab.evaluation import run_evaluation

        report = run_evaluation()
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return
    raise RuntimeError(f"Unknown command: {args.command}")


def run_openalex_ingestion(*, target: int, from_year: int) -> dict[str, Any]:
    settings = get_settings()
    with SessionLocal() as session:
        service = OpenAlexIngestionService(session, settings)
        result = service.ingest_seed(target=target, from_year=from_year)
    return {
        "run_id": str(result.run_id),
        "status": result.status,
        "corpus_count": result.corpus_count,
        "fetched_count": result.fetched_count,
        "accepted_count": result.accepted_count,
        "inserted_count": result.inserted_count,
        "updated_count": result.updated_count,
        "skipped_count": result.skipped_count,
        "error_count": result.error_count,
        "axis_stats": [asdict_axis(stats) for stats in result.axis_stats],
        "manifest_path": result.manifest_path,
    }


def asdict_axis(stats: Any) -> dict[str, Any]:
    return {
        "slug": stats.slug,
        "fetched": stats.fetched,
        "accepted": stats.accepted,
        "inserted": stats.inserted,
        "updated": stats.updated,
        "skipped": stats.skipped,
    }


if __name__ == "__main__":
    main()

