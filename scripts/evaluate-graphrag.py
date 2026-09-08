#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select

ROOT = Path(__file__).resolve().parents[1]
API_SRC = ROOT / "apps/api/src"
sys.path.insert(0, str(API_SRC))

from research_lab.config import get_settings  # noqa: E402
from research_lab.db import SessionLocal  # noqa: E402
from research_lab.embedding_selection import choose_search_embedding_provider  # noqa: E402
from research_lab.models import Paper, PaperChunk  # noqa: E402
from research_lab.research_graph import (  # noqa: E402
    GraphAugmentedRetrievalService,
    GraphRetrievalResult,
    ResearchGraphService,
    build_research_graph_service,
)
from research_lab.retrieval import HybridRetrievalService, RankedPaper  # noqa: E402


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    name: str
    query: str
    relevance_terms: tuple[str, ...]


CASES = (
    BenchmarkCase(
        "ai_adoption_firm_performance",
        "AI adoption firm performance management capabilities",
        ("ai", "adoption", "firm", "performance", "management", "capabilities"),
    ),
    BenchmarkCase(
        "generative_ai_knowledge_work",
        "generative AI knowledge worker productivity organizational performance",
        ("generative", "ai", "knowledge", "worker", "productivity", "organizational", "performance"),
    ),
    BenchmarkCase(
        "ai_governance_responsible_innovation",
        "AI governance responsible innovation organizational accountability",
        ("ai", "governance", "responsible", "innovation", "organizational", "accountability"),
    ),
    BenchmarkCase(
        "digital_transformation_dynamic_capabilities",
        "digital transformation dynamic capabilities firm innovation performance",
        ("digital", "transformation", "dynamic", "capabilities", "firm", "innovation", "performance"),
    ),
    BenchmarkCase(
        "ai_innovation_absorptive_capacity",
        "AI innovation R&D absorptive capacity technology management",
        ("ai", "innovation", "absorptive", "capacity", "technology", "management"),
    ),
)


def normalize_title(title: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", title.lower()))


def relevant_proxy(row: RankedPaper, terms: tuple[str, ...]) -> bool:
    haystack = f"{row.title} {row.abstract or ''}".lower()
    matches = sum(1 for term in terms if term.lower() in haystack)
    threshold = 2 if len(terms) >= 4 else 1
    return matches >= threshold


def full_text_ids(session: object, rows: list[RankedPaper]) -> set[str]:
    ids = [row.id for row in rows]
    if not ids:
        return set()
    values = session.scalars(  # type: ignore[attr-defined]
        select(PaperChunk.paper_id).where(PaperChunk.paper_id.in_(ids)).distinct()
    ).all()
    return {str(value) for value in values}


def summarize_run(
    session: object,
    result: GraphRetrievalResult,
    *,
    terms: tuple[str, ...],
    graph: ResearchGraphService | None,
) -> dict[str, object]:
    rows = result.rows
    titles = [normalize_title(row.title) for row in rows]
    unique_titles = len(set(titles))
    evidence_ids = full_text_ids(session, rows)
    communities: dict[object, int] = {}
    if graph is not None and rows:
        try:
            communities = graph.community_lookup([row.id for row in rows])
        except RuntimeError:
            communities = {}
    graph_only_rows = [row for row in rows if row.matched_source == "graph_expansion"]
    citation_recovered = [
        row for row in graph_only_rows if row.matched_locator and "citation" in row.matched_locator
    ]
    return {
        "returned": len(rows),
        "relevant_proxy_count": sum(1 for row in rows if relevant_proxy(row, terms)),
        "relevant_proxy_rate": round(
            sum(1 for row in rows if relevant_proxy(row, terms)) / len(rows), 4
        )
        if rows
        else 0.0,
        "full_text_evidence_count": len(evidence_ids),
        "full_text_evidence_rate": round(len(evidence_ids) / len(rows), 4) if rows else 0.0,
        "unique_title_count": unique_titles,
        "unique_title_rate": round(unique_titles / len(rows), 4) if rows else 0.0,
        "duplicate_rate": round(1 - (unique_titles / len(rows)), 4) if rows else 0.0,
        "citation_community_count": len(set(communities.values())),
        "graph_only_count": len(graph_only_rows),
        "citation_neighbor_recovered_count": len(citation_recovered),
        "graph_trace": asdict(result.trace),
        "paper_ids": [str(row.id) for row in rows],
        "titles": [row.title for row in rows],
    }


def aggregate(case_results: list[dict[str, object]], key: str) -> float:
    values = [float(result[key]) for result in case_results]
    return round(sum(values) / len(values), 4) if values else 0.0


def evaluate(limit: int) -> dict[str, object]:
    settings = get_settings()
    graph = build_research_graph_service(settings)
    if graph is None:
        raise RuntimeError("Graph evaluation requires an enabled and configured graph provider.")

    case_payloads: list[dict[str, object]] = []
    baseline_summaries: list[dict[str, object]] = []
    graph_summaries: list[dict[str, object]] = []
    with SessionLocal() as session:
        selection = choose_search_embedding_provider(session, settings, "auto")
        for case in CASES:
            baseline_service = HybridRetrievalService(session, selection.provider)
            service = GraphAugmentedRetrievalService(session, baseline_service, graph)

            baseline_started = time.perf_counter()
            baseline = service.search(
                case.query,
                graph_mode="off",
                mode="vector",
                scope="metadata",
                limit=limit,
            )
            baseline_elapsed_ms = (time.perf_counter() - baseline_started) * 1000

            graph_started = time.perf_counter()
            augmented = service.search(
                case.query,
                graph_mode="on",
                mode="vector",
                scope="metadata",
                limit=limit,
            )
            graph_elapsed_ms = (time.perf_counter() - graph_started) * 1000

            baseline_summary = summarize_run(
                session,
                baseline,
                terms=case.relevance_terms,
                graph=graph,
            )
            graph_summary = summarize_run(
                session,
                augmented,
                terms=case.relevance_terms,
                graph=graph,
            )
            baseline_summary["wall_latency_ms"] = round(baseline_elapsed_ms, 2)
            graph_summary["wall_latency_ms"] = round(graph_elapsed_ms, 2)
            baseline_summaries.append(baseline_summary)
            graph_summaries.append(graph_summary)
            case_payloads.append(
                {
                    "name": case.name,
                    "query": case.query,
                    "relevance_proxy": {
                        "type": "query_term_overlap",
                        "terms": list(case.relevance_terms),
                        "minimum_matches": 2,
                        "note": "Transparent heuristic proxy; not a human relevance judgment.",
                    },
                    "baseline": baseline_summary,
                    "graph_augmented": graph_summary,
                }
            )

        total_papers = session.scalar(select(func.count()).select_from(Paper)) or 0
        total_full_text = session.scalar(select(func.count(func.distinct(PaperChunk.paper_id)))) or 0

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "benchmark": "graphrag-retrieval-v1",
        "authoritative_evidence_source": "postgresql",
        "graph_role": "derived_read_model",
        "retrieval_flow": "vector metadata seeds -> Neo4j bounded expansion -> canonical PostgreSQL paper IDs/evidence",
        "limit_per_case": limit,
        "semantic_provider": selection.provider.name,
        "semantic_model": selection.provider.model,
        "corpus_snapshot": {
            "papers": int(total_papers),
            "full_text_papers": int(total_full_text),
        },
        "cases": case_payloads,
        "aggregate": {
            "baseline": {
                "relevant_proxy_rate": aggregate(baseline_summaries, "relevant_proxy_rate"),
                "full_text_evidence_rate": aggregate(baseline_summaries, "full_text_evidence_rate"),
                "unique_title_rate": aggregate(baseline_summaries, "unique_title_rate"),
                "duplicate_rate": aggregate(baseline_summaries, "duplicate_rate"),
                "wall_latency_ms": aggregate(baseline_summaries, "wall_latency_ms"),
            },
            "graph_augmented": {
                "relevant_proxy_rate": aggregate(graph_summaries, "relevant_proxy_rate"),
                "full_text_evidence_rate": aggregate(graph_summaries, "full_text_evidence_rate"),
                "unique_title_rate": aggregate(graph_summaries, "unique_title_rate"),
                "duplicate_rate": aggregate(graph_summaries, "duplicate_rate"),
                "wall_latency_ms": aggregate(graph_summaries, "wall_latency_ms"),
                "graph_only_count": int(sum(int(row["graph_only_count"]) for row in graph_summaries)),
                "citation_neighbor_recovered_count": int(
                    sum(int(row["citation_neighbor_recovered_count"]) for row in graph_summaries)
                ),
                "mean_expansion_count": round(
                    sum(int(row["graph_trace"]["expansion_count"]) for row in graph_summaries)  # type: ignore[index]
                    / len(graph_summaries),
                    2,
                )
                if graph_summaries
                else 0.0,
            },
        },
        "limitations": [
            (
                "Relevant-paper coverage is a transparent query-term-overlap proxy, "
                "not a human-labeled relevance judgment."
            ),
            (
                "Latency includes local embedding generation, PostgreSQL retrieval, graph expansion, "
                "and canonical rematerialization."
            ),
            "The graph is a rebuildable projection and is never treated as claim-level evidence.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare baseline vector retrieval with optional GraphRAG augmentation"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    if args.limit < 1 or args.limit > 50:
        raise SystemExit("--limit must be between 1 and 50")
    result = evaluate(args.limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "aggregate": result["aggregate"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
