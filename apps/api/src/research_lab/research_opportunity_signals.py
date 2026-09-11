from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from sqlalchemy import and_, case, delete, func, select
from sqlalchemy.orm import Session, aliased

from research_lab.models import Paper, ResearchOpportunity, ResearchSignalExtract

SIGNAL_OPPORTUNITY_VERSION = "signal_opportunity_v1"
PARTNER_TYPES = ("dataset", "method", "evaluation_metric", "future_research")


@dataclass(frozen=True, slots=True)
class SignalOpportunityResult:
    generated: int
    upserted: int
    deleted_previous: int
    dry_run: bool

    def asdict(self) -> dict[str, int | bool]:
        return asdict(self)


def refresh_signal_research_opportunities(
    session: Session,
    *,
    limit: int = 24,
    min_intersection: int = 3,
    replace_existing: bool = True,
    dry_run: bool = False,
) -> SignalOpportunityResult:
    """Create Research Opportunities from normalized Research Card signal intersections.

    Coverage-gap opportunities ask "where is the corpus sparse?". These rows ask a
    more useful question: "which repeated limitation is already intersecting with a
    data/method/evaluation/future-research signal enough to become testable?".
    """

    generated_at = datetime.now(UTC)
    min_intersection = max(min_intersection, 1)
    rows = _intersection_rows(session, min_intersection=min_intersection, limit=max(limit * 4, limit))
    opportunities = [_row_to_opportunity(row, generated_at) for row in rows[: max(limit, 1)]]
    deleted_previous = 0
    if dry_run:
        return SignalOpportunityResult(
            generated=len(opportunities),
            upserted=0,
            deleted_previous=0,
            dry_run=True,
        )

    if replace_existing:
        delete_result = session.execute(
            delete(ResearchOpportunity).where(ResearchOpportunity.slug.like("signal-%"))
        )
        deleted_previous = int(delete_result.rowcount or 0)
        session.flush()

    upserted = 0
    for opportunity in opportunities:
        stored = session.scalar(select(ResearchOpportunity).where(ResearchOpportunity.slug == opportunity.slug))
        if stored is None:
            session.add(opportunity)
        else:
            stored.title = opportunity.title
            stored.hypothesis = opportunity.hypothesis
            stored.rationale = opportunity.rationale
            stored.axis_slug = opportunity.axis_slug
            stored.coverage_count = opportunity.coverage_count
            stored.adjacent_count = opportunity.adjacent_count
            stored.signals = opportunity.signals
            stored.recommended_method = opportunity.recommended_method
            stored.generated_at = generated_at
        upserted += 1
    session.commit()
    return SignalOpportunityResult(
        generated=len(opportunities),
        upserted=upserted,
        deleted_previous=deleted_previous,
        dry_run=False,
    )


def _intersection_rows(
    session: Session,
    *,
    min_intersection: int,
    limit: int,
) -> list[dict[str, object]]:
    limitation = aliased(ResearchSignalExtract)
    partner = aliased(ResearchSignalExtract)
    current_year = session.scalar(select(func.max(Paper.publication_year))) or datetime.now(UTC).year
    recent_start = int(current_year) - 1
    intersection_count = func.count(func.distinct(limitation.paper_id))
    recent_count = func.count(
        func.distinct(
            case(
                (
                    and_(
                        Paper.publication_year >= recent_start,
                        Paper.publication_year <= int(current_year),
                    ),
                    limitation.paper_id,
                )
            )
        )
    )
    rows = session.execute(
        select(
            limitation.label.label("limitation_label"),
            limitation.normalized_label.label("limitation_key"),
            partner.signal_type.label("partner_type"),
            partner.label.label("partner_label"),
            partner.normalized_label.label("partner_key"),
            intersection_count.label("intersection_count"),
            recent_count.label("recent_count"),
            func.count(func.distinct(limitation.research_card_id)).label("card_count"),
            func.count(func.distinct(limitation.chunk_id)).label("located_chunk_count"),
            func.min(limitation.evidence_text).label("limitation_evidence"),
            func.min(partner.evidence_text).label("partner_evidence"),
            func.min(limitation.source_locator).label("limitation_locator"),
            func.min(partner.source_locator).label("partner_locator"),
        )
        .join(partner, limitation.paper_id == partner.paper_id)
        .join(Paper, Paper.id == limitation.paper_id)
        .where(
            limitation.signal_type == "limitation",
            partner.signal_type.in_(PARTNER_TYPES),
            limitation.support_status == "supported",
            partner.support_status == "supported",
        )
        .group_by(
            limitation.label,
            limitation.normalized_label,
            partner.signal_type,
            partner.label,
            partner.normalized_label,
        )
        .having(intersection_count >= min_intersection)
        .order_by(
            recent_count.desc(),
            intersection_count.desc(),
            partner.signal_type,
            partner.label,
        )
        .limit(limit)
    ).mappings()
    return [dict(row) for row in rows]


def _row_to_opportunity(row: dict[str, object], generated_at: datetime) -> ResearchOpportunity:
    limitation = str(row["limitation_label"])
    partner_type = str(row["partner_type"])
    partner = str(row["partner_label"])
    intersection_count = int(row["intersection_count"] or 0)
    recent_count = int(row["recent_count"] or 0)
    card_count = int(row["card_count"] or 0)
    located_chunk_count = int(row["located_chunk_count"] or 0)
    opportunity_label = _partner_phrase(partner_type, partner)
    slug = _signal_slug(limitation, partner_type, partner)
    recommended_method = partner if partner_type == "method" else _recommended_method(partner_type, partner)
    return ResearchOpportunity(
        slug=slug,
        title=f"Test {limitation.lower()} through {opportunity_label}",
        hypothesis=(
            f"A useful next study can turn the repeated limitation '{limitation}' into a testable design "
            f"by using {opportunity_label}."
        ),
        rationale=(
            f"The local Research Card layer already contains {intersection_count} papers where '{limitation}' "
            f"co-occurs with {opportunity_label}. This is not proof of a field gap; it is a grounded lead for "
            "a falsification search and research-design audit."
        ),
        axis_slug=None,
        evidence_status="insufficient_evidence",
        coverage_count=intersection_count,
        adjacent_count=max(recent_count, 0),
        signals={
            "source": "research_signal_extracts",
            "version": SIGNAL_OPPORTUNITY_VERSION,
            "opportunity_kind": "signal_intersection",
            "limitation": limitation,
            "partner_type": partner_type,
            "partner_label": partner,
            "intersection_papers": intersection_count,
            "recent_intersection_papers": recent_count,
            "research_cards": card_count,
            "located_chunks": located_chunk_count,
            "limitation_evidence": _truncate(str(row.get("limitation_evidence") or "")),
            "partner_evidence": _truncate(str(row.get("partner_evidence") or "")),
            "limitation_locator": row.get("limitation_locator"),
            "partner_locator": row.get("partner_locator"),
            "candidate_not_conclusion": True,
            "requires_falsification_search": True,
        },
        recommended_method=recommended_method,
        generated_at=generated_at,
    )


def _signal_slug(limitation: str, partner_type: str, partner: str) -> str:
    raw = f"signal-{limitation}-{partner_type}-{partner}"
    slug = re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-")
    return slug[:160]


def _partner_phrase(partner_type: str, label: str) -> str:
    if partner_type == "dataset":
        return f"{label.lower()}"
    if partner_type == "method":
        return f"{label.lower()}"
    if partner_type == "evaluation_metric":
        return f"the {label.lower()} evaluation criterion"
    if partner_type == "future_research":
        return f"a {label.lower()} follow-up design"
    return label.lower()


def _recommended_method(partner_type: str, label: str) -> str:
    if partner_type == "dataset":
        return f"Design around {label.lower()} with explicit construct validity checks"
    if partner_type == "evaluation_metric":
        return f"Operationalize and validate {label.lower()} before causal claims"
    if partner_type == "future_research":
        return f"Use {label.lower()} as the first falsification protocol"
    return "Focused evidence review followed by a falsifiable empirical design"


def _truncate(value: str, *, max_chars: int = 360) -> str:
    compact = " ".join(value.split())
    if len(compact) <= max_chars:
        return compact
    return f"{compact[: max_chars - 1].rstrip()}…"
