from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any

from research_lab.db import SessionLocal
from research_lab.retrieval import HybridRetrievalService, SearchMode

PROJECT_ROOT = Path(__file__).resolve().parents[4]
GOLDEN_QUERIES_PATH = PROJECT_ROOT / "evaluation" / "golden_queries.json"
REPORT_PATH = PROJECT_ROOT / "artifacts" / "evaluation" / "retrieval-evaluation.json"


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    return len(set(retrieved[:k]) & relevant) / len(relevant)


def ndcg_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, paper_id in enumerate(retrieved[:k], start=1)
        if paper_id in relevant
    )
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / idcg if idcg else 0.0


def reciprocal_rank(retrieved: list[str], relevant: set[str]) -> float:
    for rank, paper_id in enumerate(retrieved, start=1):
        if paper_id in relevant:
            return 1.0 / rank
    return 0.0


def run_evaluation() -> dict[str, Any]:
    cases = json.loads(GOLDEN_QUERIES_PATH.read_text(encoding="utf-8"))
    modes: tuple[SearchMode, ...] = ("lexical", "vector", "hybrid")
    per_mode: dict[str, list[dict[str, Any]]] = {mode: [] for mode in modes}

    with SessionLocal() as session:
        service = HybridRetrievalService(session)
        for case in cases:
            relevant = set(case["relevant_openalex_ids"])
            for search_mode in modes:
                ranked_rows = service.search(case["query"], mode=search_mode, limit=10)
                retrieved = [row.openalex_id for row in ranked_rows if row.openalex_id]
                per_mode[search_mode].append(
                    {
                        "id": case["id"],
                        "query": case["query"],
                        "relevant": sorted(relevant),
                        "retrieved": retrieved,
                        "recall_at_5": recall_at_k(retrieved, relevant, 5),
                        "ndcg_at_10": ndcg_at_k(retrieved, relevant, 10),
                        "reciprocal_rank": reciprocal_rank(retrieved, relevant),
                    }
                )

    summary: dict[str, dict[str, float]] = {}
    for mode_name, metric_rows in per_mode.items():
        summary[mode_name] = {
            "mean_recall_at_5": mean(row["recall_at_5"] for row in metric_rows),
            "mean_ndcg_at_10": mean(row["ndcg_at_10"] for row in metric_rows),
            "mrr_at_10": mean(row["reciprocal_rank"] for row in metric_rows),
        }

    report: dict[str, Any] = {
        "evaluation_set": "small manually curated evaluation set",
        "query_count": len(cases),
        "generated_at": datetime.now(UTC).isoformat(),
        "summary": summary,
        "queries": per_mode,
        "limitations": [
            "Judgments are title/abstract-level manual labels from the 529-paper seed corpus.",
            "The set is too small for claims of general retrieval superiority.",
            "Local hash embeddings are deterministic mock embeddings, not a production semantic model.",
        ],
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report
