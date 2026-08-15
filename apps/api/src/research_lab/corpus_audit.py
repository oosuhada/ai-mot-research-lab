from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from research_lab.models import Paper
from research_lab.taxonomy import RESEARCH_AXES, text_matches_axis


def audit_corpus(session: Session) -> dict[str, Any]:
    """Measure coverage before tuning collection rules; never mutates corpus records."""

    papers = session.execute(select(Paper.title, Paper.abstract, Paper.publication_year)).all()
    year_counts = Counter(year for _, _, year in papers if year is not None)
    abstract_count = int(
        session.scalar(select(func.count()).select_from(Paper).where(Paper.abstract.is_not(None))) or 0
    )
    matched = 0
    unmatched_examples: list[str] = []
    for title, abstract, _ in papers:
        text = f"{title}\n{abstract or ''}"
        if any(text_matches_axis(text, axis) for axis in RESEARCH_AXES):
            matched += 1
        elif len(unmatched_examples) < 20:
            unmatched_examples.append(title)

    total = len(papers)
    newest_year = max(year_counts, default=None)
    newest_count = year_counts.get(newest_year, 0) if newest_year is not None else 0
    return {
        "paper_count": total,
        "abstract_count": abstract_count,
        "abstract_coverage_pct": _pct(abstract_count, total),
        "taxonomy_relevant_count": matched,
        "taxonomy_relevant_pct": _pct(matched, total),
        "publication_years": dict(sorted(year_counts.items(), reverse=True)),
        "newest_year": newest_year,
        "newest_year_share_pct": _pct(newest_count, total),
        "unmatched_title_examples": unmatched_examples,
        "collection_policy": "round_robin_axis_year_pages",
    }


def _pct(value: int, total: int) -> float:
    return round((value / total * 100.0) if total else 0.0, 2)
