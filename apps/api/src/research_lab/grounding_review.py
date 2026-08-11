from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from research_lab.chat import answer_chat
from research_lab.db import SessionLocal
from research_lab.schemas import ChatRequest

PROJECT_ROOT = Path(__file__).resolve().parents[4]
GOLDEN_QUERIES_PATH = PROJECT_ROOT / "evaluation" / "golden_queries.json"
DEFAULT_REVIEW_PATH = PROJECT_ROOT / "artifacts" / "evaluation" / "grounding-human-review.csv"

HUMAN_LABELS = {"supported", "contradicted", "insufficient_evidence"}
FIELDNAMES = (
    "review_id",
    "query_id",
    "query",
    "claim_text",
    "system_claim_kind",
    "system_support_status",
    "citation_index",
    "paper_id",
    "paper_title",
    "doi",
    "source_locator",
    "evidence_excerpt",
    "human_label",
    "human_note",
)


def export_grounding_review(path: Path = DEFAULT_REVIEW_PATH) -> dict[str, object]:
    """Export a local-only review queue; never assigns semantic labels automatically."""

    cases = json.loads(GOLDEN_QUERIES_PATH.read_text(encoding="utf-8"))
    rows: list[dict[str, object]] = []
    with SessionLocal() as session:
        for case in cases:
            response = answer_chat(
                session,
                ChatRequest(question=case["query"], scope_type="corpus", max_papers=5),
            )
            citations = {citation.index: citation for citation in response.citations}
            for paragraph_index, paragraph in enumerate(response.paragraphs, start=1):
                if paragraph.support_status == "insufficient_evidence":
                    continue
                for citation_index in paragraph.citation_indexes:
                    citation = citations.get(citation_index)
                    if citation is None:
                        continue
                    rows.append(
                        {
                            "review_id": f"{case['id']}-p{paragraph_index}-c{citation_index}",
                            "query_id": case["id"],
                            "query": case["query"],
                            "claim_text": paragraph.text,
                            "system_claim_kind": paragraph.claim_kind,
                            "system_support_status": paragraph.support_status,
                            "citation_index": citation.index,
                            "paper_id": str(citation.paper_id),
                            "paper_title": citation.paper_title,
                            "doi": citation.doi or "",
                            "source_locator": citation.source_locator,
                            "evidence_excerpt": citation.excerpt,
                            "human_label": "",
                            "human_note": "",
                        }
                    )

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    return {
        "path": str(path),
        "review_pairs": len(rows),
        "human_labels_assigned": 0,
        "semantic_precision": None,
        "status": "awaiting_human_review",
    }


def score_grounding_review(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return score_grounding_rows(rows)


def score_grounding_rows(rows: list[dict[str, Any]]) -> dict[str, object]:
    reviewed: list[dict[str, Any]] = []
    for row in rows:
        label = str(row.get("human_label") or "").strip()
        if not label:
            continue
        if label not in HUMAN_LABELS:
            raise ValueError(f"Invalid human_label {label!r}; expected one of {sorted(HUMAN_LABELS)}")
        reviewed.append(row)

    supported = sum(1 for row in reviewed if row["human_label"] == "supported")
    contradicted = sum(1 for row in reviewed if row["human_label"] == "contradicted")
    insufficient = sum(1 for row in reviewed if row["human_label"] == "insufficient_evidence")
    reviewed_count = len(reviewed)
    total = len(rows)
    return {
        "review_pairs": total,
        "reviewed_pairs": reviewed_count,
        "review_coverage": reviewed_count / total if total else 0.0,
        "human_reviewed_semantic_support_precision": (
            supported / reviewed_count if reviewed_count else None
        ),
        "supported_pairs": supported,
        "contradicted_pairs": contradicted,
        "insufficient_evidence_pairs": insufficient,
        "status": "scored" if reviewed_count else "awaiting_human_review",
        "note": (
            "This is a human evidence-pair judgment. The system never fills human_label automatically."
        ),
    }
