from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from research_lab.citation_graph import resolve_local_citation_edges
from research_lab.config import get_settings
from research_lab.db import SessionLocal
from research_lab.embedding_maintenance import backfill_embeddings
from research_lab.embeddings import build_embedding_provider
from research_lab.ingestion.service import OpenAlexIngestionService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="research-lab")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest = subparsers.add_parser("ingest-openalex", help="Build or refresh the scoped OpenAlex seed corpus")
    ingest.add_argument("--target", type=int, default=600, help="Minimum design target for the seed corpus")
    ingest.add_argument("--from-year", type=int, default=2018, help="Default publication lower bound")

    expand = subparsers.add_parser(
        "expand-corpus",
        help="Run one resumable OpenAlex batch toward a larger recent-paper corpus",
    )
    expand.add_argument("--target-total", type=int, default=100_000)
    expand.add_argument("--from-year", type=int, default=2017)
    expand.add_argument("--to-year", type=int, default=2026)
    expand.add_argument("--max-pages", type=int, default=5)
    subparsers.add_parser(
        "corpus-expansion-status",
        help="Show checkpointed progress for the long-running corpus expansion",
    )

    subparsers.add_parser(
        "backfill-methodologies",
        help="Apply transparent keyword-based methodology labels to the current corpus",
    )
    subparsers.add_parser(
        "backfill-subaxes",
        help="Apply transparent keyword-based sub-area labels and evidence-depth profiles",
    )
    refresh = subparsers.add_parser(
        "refresh-intelligence",
        help="Refresh evidence-depth, full-text priority, daily discovery, and opportunity snapshots",
    )
    refresh.add_argument("--discovery-days", type=int, default=2)
    discover = subparsers.add_parser(
        "discover-daily",
        help="Discover recent AI × MOT publications without changing corpus-expansion state",
    )
    discover.add_argument("--lookback-days", type=int, default=3)
    discover.add_argument("--max-pages-per-axis", type=int, default=2)
    enrich = subparsers.add_parser(
        "enrich-full-text",
        help="Process a bounded batch of prioritized rights-safe open-access PDFs",
    )
    enrich.add_argument("--max-items", type=int, default=3)
    enrich.add_argument("--max-pdf-bytes", type=int, default=30_000_000)
    translation_export = subparsers.add_parser(
        "export-translation-queue",
        help="Export untranslated abstracts for an authorized external translation batch",
    )
    translation_export.add_argument("--locale", default="ko")
    translation_export.add_argument("--limit", type=int, default=100)
    translation_export.add_argument("--output", type=Path, required=True)
    translation_import = subparsers.add_parser(
        "import-localizations",
        help="Import provenance-tagged translated titles, abstracts, and keywords",
    )
    translation_import.add_argument("--input", type=Path, required=True)
    subparsers.add_parser("evaluate", help="Run the committed small-set retrieval/evidence evaluation")
    review_export = subparsers.add_parser(
        "grounding-review-export",
        help="Export a local CSV queue for human claim-to-source review",
    )
    review_export.add_argument("--output", type=Path, default=None)
    review_score = subparsers.add_parser(
        "grounding-review-score",
        help="Score only the human labels already filled in a grounding-review CSV",
    )
    review_score.add_argument("--input", type=Path, required=True)
    benchmark = subparsers.add_parser(
        "benchmark-retrieval",
        help="Measure warm local hybrid-search latency over representative AI × MOT queries",
    )
    benchmark.add_argument("--provider", choices=("local_hash", "fastembed"), default="local_hash")
    benchmark.add_argument("--repeats", type=int, default=3)
    subparsers.add_parser(
        "resolve-citations",
        help="Resolve OpenAlex citation IDs to canonical papers already present in the local corpus",
    )
    embedding_backfill = subparsers.add_parser(
        "backfill-embeddings",
        help="Backfill paper/chunk vectors for a selected embedding provider",
    )
    embedding_backfill.add_argument(
        "--provider",
        choices=("local_hash", "fastembed"),
        default=None,
        help="Override EMBEDDING_PROVIDER for this run",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "ingest-openalex":
        result = run_openalex_ingestion(target=args.target, from_year=args.from_year)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    if args.command == "expand-corpus":
        from research_lab.corpus_expansion import CorpusExpansionWorker

        settings = get_settings()
        with SessionLocal() as session:
            worker = CorpusExpansionWorker(session, settings)
            result = worker.run_batch(
                target_total=args.target_total,
                from_year=args.from_year,
                to_year=args.to_year,
                max_pages=args.max_pages,
            )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    if args.command == "corpus-expansion-status":
        from research_lab.corpus_expansion import CorpusExpansionWorker

        settings = get_settings()
        with SessionLocal() as session:
            worker = CorpusExpansionWorker(session, settings)
            result = worker.status()
            worker.close()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    if args.command == "evaluate":
        from research_lab.evaluation import run_evaluation

        report = run_evaluation()
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return
    if args.command == "grounding-review-export":
        from research_lab.grounding_review import DEFAULT_REVIEW_PATH, export_grounding_review

        review = export_grounding_review(args.output or DEFAULT_REVIEW_PATH)
        print(json.dumps(review, indent=2, ensure_ascii=False))
        return
    if args.command == "grounding-review-score":
        from research_lab.grounding_review import score_grounding_review

        review_score = score_grounding_review(args.input)
        print(json.dumps(review_score, indent=2, ensure_ascii=False))
        return
    if args.command == "benchmark-retrieval":
        from dataclasses import asdict

        from research_lab.observability import benchmark_retrieval

        settings = get_settings()
        with SessionLocal() as session:
            benchmark_result = benchmark_retrieval(
                session,
                settings,
                provider_name=args.provider,
                repeats=args.repeats,
            )
        print(json.dumps(asdict(benchmark_result), indent=2, ensure_ascii=False))
        return
    if args.command == "backfill-methodologies":
        settings = get_settings()
        with SessionLocal() as session:
            service = OpenAlexIngestionService(session, settings)
            count = service.backfill_methodologies()
        print(json.dumps({"status": "completed", "papers_processed": count}, indent=2))
        return
    if args.command == "backfill-subaxes":
        settings = get_settings()
        with SessionLocal() as session:
            service = OpenAlexIngestionService(session, settings)
            count = service.backfill_subaxes()
        print(json.dumps({"status": "completed", "papers_processed": count}, indent=2))
        return
    if args.command == "refresh-intelligence":
        from research_lab.corpus_intelligence import refresh_corpus_intelligence

        with SessionLocal() as session:
            refresh_result = refresh_corpus_intelligence(
                session,
                discovery_days=max(args.discovery_days, 1),
            )
        print(json.dumps({"status": "completed", **refresh_result}, indent=2))
        return
    if args.command == "discover-daily":
        from research_lab.daily_discovery import DailyDiscoveryWorker

        settings = get_settings()
        with SessionLocal() as session:
            discovery_result = DailyDiscoveryWorker(session, settings).run(
                lookback_days=max(args.lookback_days, 1),
                max_pages_per_axis=max(args.max_pages_per_axis, 1),
            )
        print(json.dumps(discovery_result, indent=2, ensure_ascii=False))
        return
    if args.command == "enrich-full-text":
        from research_lab.full_text_enrichment import FullTextEnrichmentWorker

        settings = get_settings()
        with SessionLocal() as session:
            enrichment_result = FullTextEnrichmentWorker(session, settings).run(
                max_items=max(args.max_items, 1),
                max_pdf_bytes=max(args.max_pdf_bytes, 1_000_000),
            )
        print(json.dumps({"status": "completed", **enrichment_result}, indent=2))
        return
    if args.command == "export-translation-queue":
        from research_lab.corpus_intelligence import translation_queue

        with SessionLocal() as session:
            queue = translation_queue(
                session,
                locale=args.locale,
                limit=max(1, args.limit),
            )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(queue, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps({"status": "completed", "records": len(queue), "output": str(args.output)}, indent=2))
        return
    if args.command == "import-localizations":
        from research_lab.corpus_intelligence import import_localizations

        payload = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("Localization import must be a JSON list")
        with SessionLocal() as session:
            imported = import_localizations(session, payload)
        print(json.dumps({"status": "completed", "records": imported}, indent=2))
        return
    if args.command == "resolve-citations":
        with SessionLocal() as session:
            resolution = resolve_local_citation_edges(session)
        print(
            json.dumps(
                {
                    "status": "completed",
                    "matched_edges": resolution.matched_edges,
                    "remaining_external_edges": resolution.remaining_external_edges,
                },
                indent=2,
            )
        )
        return
    if args.command == "backfill-embeddings":
        settings = get_settings()
        provider = build_embedding_provider(settings, args.provider)
        with SessionLocal() as session:
            embedding_result = backfill_embeddings(session, provider)
        print(
            json.dumps(
                {
                    "status": "completed",
                    "provider": provider.name,
                    "model": provider.model,
                    "papers_processed": embedding_result.papers_processed,
                    "paper_embeddings_inserted": embedding_result.paper_embeddings_inserted,
                    "paper_embeddings_updated": embedding_result.paper_embeddings_updated,
                    "chunks_updated": embedding_result.chunks_updated,
                },
                indent=2,
            )
        )
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
