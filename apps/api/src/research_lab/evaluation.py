from __future__ import annotations

import json
import math
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any

from sqlalchemy import func, select

from research_lab.chat import answer_chat
from research_lab.config import get_settings
from research_lab.db import SessionLocal
from research_lab.embeddings import build_embedding_provider
from research_lab.models import PaperEmbedding
from research_lab.retrieval import HybridRetrievalService, SearchMode
from research_lab.schemas import ChatRequest

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


def _metric_summary(rows: list[dict[str, Any]]) -> dict[str, float]:
    return {
        "mean_recall_at_5": mean(row["recall_at_5"] for row in rows),
        "mean_recall_at_10": mean(row["recall_at_10"] for row in rows),
        "mean_ndcg_at_10": mean(row["ndcg_at_10"] for row in rows),
        "mrr_at_10": mean(row["reciprocal_rank"] for row in rows),
    }


def _provider_metrics(cases: list[dict[str, Any]], provider_name: str) -> dict[str, dict[str, float]]:
    settings = get_settings()
    provider = build_embedding_provider(settings, provider_name)
    per_mode: dict[str, list[dict[str, Any]]] = {"vector": [], "hybrid": []}
    with SessionLocal() as session:
        service = HybridRetrievalService(session, provider)
        for case in cases:
            relevant = set(case["relevant_openalex_ids"])
            for mode in ("vector", "hybrid"):
                rows = service.search(case["query"], mode=mode, limit=10)
                retrieved = [row.openalex_id for row in rows if row.openalex_id]
                per_mode[mode].append(
                    {
                        "recall_at_5": recall_at_k(retrieved, relevant, 5),
                        "recall_at_10": recall_at_k(retrieved, relevant, 10),
                        "ndcg_at_10": ndcg_at_k(retrieved, relevant, 10),
                        "reciprocal_rank": reciprocal_rank(retrieved, relevant),
                    }
                )
    return {mode: _metric_summary(rows) for mode, rows in per_mode.items()}


def run_evaluation() -> dict[str, Any]:
    cases = json.loads(GOLDEN_QUERIES_PATH.read_text(encoding="utf-8"))
    modes: tuple[SearchMode, ...] = ("lexical", "vector", "hybrid")
    per_mode: dict[str, list[dict[str, Any]]] = {mode: [] for mode in modes}

    grounding_totals = {
        "assertive_paragraphs": 0,
        "assertive_with_citations": 0,
        "invalid_citation_indexes": 0,
    }

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
                        "recall_at_10": recall_at_k(retrieved, relevant, 10),
                        "ndcg_at_10": ndcg_at_k(retrieved, relevant, 10),
                        "reciprocal_rank": reciprocal_rank(retrieved, relevant),
                    }
                )

            chat = answer_chat(
                session,
                ChatRequest(question=case["query"], scope_type="corpus", max_papers=5),
            )
            valid_indexes = {citation.index for citation in chat.citations}
            for paragraph in chat.paragraphs:
                if paragraph.support_status == "insufficient_evidence":
                    continue
                grounding_totals["assertive_paragraphs"] += 1
                if paragraph.citation_indexes:
                    grounding_totals["assertive_with_citations"] += 1
                grounding_totals["invalid_citation_indexes"] += sum(
                    1
                    for index in paragraph.citation_indexes
                    if index not in valid_indexes
                )

    summary = {mode_name: _metric_summary(metric_rows) for mode_name, metric_rows in per_mode.items()}

    provider_comparison: dict[str, dict[str, dict[str, float]]] = {
        "local_hash": {
            "vector": summary["vector"],
            "hybrid": summary["hybrid"],
        }
    }
    with SessionLocal() as session:
        fastembed_count = session.scalar(
            select(func.count()).select_from(PaperEmbedding).where(PaperEmbedding.provider == "fastembed")
        ) or 0
    if fastembed_count:
        with suppress(RuntimeError):
            provider_comparison["fastembed"] = _provider_metrics(cases, "fastembed")

    assertive = grounding_totals["assertive_paragraphs"]
    cited = grounding_totals["assertive_with_citations"]
    grounding_summary = {
        "structural_claim_to_evidence_coverage": cited / assertive if assertive else 1.0,
        "structural_unsupported_claim_rate": (assertive - cited) / assertive if assertive else 0.0,
        "invalid_citation_indexes": grounding_totals["invalid_citation_indexes"],
        "semantic_citation_precision": None,
        "semantic_citation_precision_status": "requires human claim-to-source review",
    }

    report: dict[str, Any] = {
        "evaluation_set": "small manually curated evaluation set",
        "query_count": len(cases),
        "generated_at": datetime.now(UTC).isoformat(),
        "summary": summary,
        "embedding_provider_comparison": provider_comparison,
        "grounding_summary": grounding_summary,
        "queries": per_mode,
        "limitations": [
            "Judgments are title/abstract-level manual labels from the 529-paper seed corpus.",
            "The set is too small for claims of general retrieval superiority.",
            "Local hash embeddings are deterministic mock embeddings, not a production semantic model.",
            "Structural grounding checks citation attachment and index validity; "
            "semantic entailment requires human review.",
            "Full-text evaluation remains a small operational fixture until more permitted PDFs are locally available.",
        ],
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report
