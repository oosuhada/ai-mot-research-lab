from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from sqlalchemy import and_, case, delete, desc, func, select
from sqlalchemy.orm import Session, aliased

from research_lab.models import (
    GapAnalysis,
    Paper,
    ReadingQueue,
    ResearchDesign,
    ResearchDirection,
    ResearchOpportunity,
    ResearchQuestion,
    ResearchQuestionNote,
    ResearchQuestionPaper,
    ResearchQuestionSavedSearch,
    ResearchSignalExtract,
    SavedSearch,
)
from research_lab.research_questions import get_research_question
from research_lab.schemas import ResearchQuestionResponse

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


def create_question_from_research_opportunity(
    session: Session,
    slug: str,
    *,
    max_papers: int = 8,
) -> ResearchQuestionResponse:
    """Turn an opportunity lead into a usable research-writing workspace."""

    opportunity = session.scalar(select(ResearchOpportunity).where(ResearchOpportunity.slug == slug))
    if opportunity is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Research opportunity not found")

    signals = opportunity.signals or {}
    limitation = _signal_text(signals.get("limitation"))
    partner_type = _signal_text(signals.get("partner_type"))
    partner_label = _signal_text(signals.get("partner_label"))
    source = _signal_text(signals.get("source")) or "coverage_gap"
    title = _question_title(opportunity, limitation, partner_label)
    question_text = _question_text(opportunity, limitation, partner_type, partner_label)
    primary_query = _primary_query(opportunity, limitation, partner_label)
    falsification_query = _falsification_query(limitation, partner_label)
    papers = _representative_signal_papers(
        session,
        limitation=limitation,
        partner_type=partner_type,
        partner_label=partner_label,
        limit=max(max_papers, 1),
    )

    question = ResearchQuestion(
        title=title,
        question_text=question_text,
        motivation=(
            "Created from a Research Opportunity so the user can move from trend sensing "
            "to a falsifiable study design. The opportunity should be treated as a lead, not proof of a gap."
        ),
        scope_notes=_scope_notes(limitation, partner_type, partner_label, source),
        importance_notes=opportunity.rationale,
        evidence_status="insufficient_evidence",
        uncertainty_notes=_uncertainty_notes(opportunity, limitation, partner_type, partner_label),
        status="exploring",
    )
    session.add(question)
    session.flush()

    saved_searches = _create_saved_searches(
        session,
        question.id,
        opportunity,
        primary_query=primary_query,
        falsification_query=falsification_query,
    )
    _attach_representative_papers(session, question.id, papers, opportunity)
    direction = _create_question_direction(
        session,
        question.id,
        opportunity,
        limitation,
        partner_type,
        partner_label,
    )
    session.flush()
    _create_question_design(
        session,
        question.id,
        direction.id,
        limitation,
        partner_type,
        partner_label,
    )
    _create_gap_canvas(session, question.id, opportunity, primary_query, falsification_query)
    _create_import_note(
        session,
        question.id,
        opportunity,
        papers,
        saved_searches=saved_searches,
    )
    session.commit()
    return get_research_question(session, question.id)


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


def _signal_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _question_title(
    opportunity: ResearchOpportunity,
    limitation: str | None,
    partner_label: str | None,
) -> str:
    if limitation and partner_label:
        return f"{limitation}: testable design using {partner_label}"
    return opportunity.title[:500]


def _question_text(
    opportunity: ResearchOpportunity,
    limitation: str | None,
    partner_type: str | None,
    partner_label: str | None,
) -> str:
    if limitation and partner_type and partner_label:
        return (
            f"How can the repeated limitation of {limitation.lower()} be tested or reduced "
            f"in AI × MOT research by using {partner_label.lower()} as a {partner_type.replace('_', ' ')}?"
        )
    return f"How can this research opportunity be turned into a falsifiable AI × MOT study: {opportunity.title}?"


def _primary_query(
    opportunity: ResearchOpportunity,
    limitation: str | None,
    partner_label: str | None,
) -> str:
    parts = [value for value in (limitation, partner_label) if value]
    if parts:
        return " AI ".join(parts) + " AI management technology innovation"
    return f"{opportunity.title} AI management technology innovation"


def _falsification_query(limitation: str | None, partner_label: str | None) -> str:
    if limitation and partner_label:
        return (
            f"{limitation} {partner_label} replication contradictory evidence alternative explanation "
            "AI adoption management"
        )
    return "AI management research gap replication contradictory evidence alternative explanation"


def _scope_notes(
    limitation: str | None,
    partner_type: str | None,
    partner_label: str | None,
    source: str,
) -> str:
    if limitation and partner_type and partner_label:
        return (
            f"Scope imported from {source}: investigate '{limitation}' against "
            f"{partner_type.replace('_', ' ')} signal '{partner_label}'. Start with linked papers, then broaden search."
        )
    return (
        "Scope imported from a coverage-derived opportunity; validate the field boundary "
        "before narrowing the design."
    )


def _uncertainty_notes(
    opportunity: ResearchOpportunity,
    limitation: str | None,
    partner_type: str | None,
    partner_label: str | None,
) -> str:
    uncertainty = [
        "The opportunity is an automated lead and must be falsified before being treated as a research gap.",
        "Check whether broader databases already resolve this limitation.",
    ]
    if limitation and partner_type and partner_label:
        uncertainty.append(
            f"Verify whether '{partner_label}' genuinely addresses '{limitation}' or merely co-occurs in the corpus."
        )
    if opportunity.signals:
        uncertainty.append(f"Local signal metadata: {opportunity.signals.get('opportunity_kind', 'opportunity')}")
    return "\n".join(uncertainty)


def _create_saved_searches(
    session: Session,
    question_id: object,
    opportunity: ResearchOpportunity,
    *,
    primary_query: str,
    falsification_query: str,
) -> list[SavedSearch]:
    searches = [
        SavedSearch(
            name=f"Opportunity evidence: {opportunity.title[:180]}",
            query_text=primary_query,
            filters={
                "source": "research_opportunity",
                "opportunity_slug": opportunity.slug,
                "mode": "vector",
                "scope": "abstract",
            },
        ),
        SavedSearch(
            name=f"Falsification search: {opportunity.title[:170]}",
            query_text=falsification_query,
            filters={
                "source": "research_opportunity_falsification",
                "opportunity_slug": opportunity.slug,
                "mode": "vector",
                "scope": "abstract",
            },
        ),
    ]
    session.add_all(searches)
    session.flush()
    for saved in searches:
        session.add(ResearchQuestionSavedSearch(research_question_id=question_id, saved_search_id=saved.id))
    return searches


def _representative_signal_papers(
    session: Session,
    *,
    limitation: str | None,
    partner_type: str | None,
    partner_label: str | None,
    limit: int,
) -> list[tuple[Paper, str | None, str | None, str | None, str | None]]:
    if not (limitation and partner_type and partner_label):
        return []
    limitation_extract = aliased(ResearchSignalExtract)
    partner_extract = aliased(ResearchSignalExtract)
    rows = session.execute(
        select(
            Paper,
            func.min(limitation_extract.evidence_text),
            func.min(limitation_extract.source_locator),
            func.min(partner_extract.evidence_text),
            func.min(partner_extract.source_locator),
        )
        .join(limitation_extract, limitation_extract.paper_id == Paper.id)
        .join(partner_extract, partner_extract.paper_id == Paper.id)
        .where(
            limitation_extract.signal_type == "limitation",
            limitation_extract.label == limitation,
            partner_extract.signal_type == partner_type,
            partner_extract.label == partner_label,
            limitation_extract.support_status == "supported",
            partner_extract.support_status == "supported",
        )
        .group_by(Paper.id)
        .order_by(desc(Paper.publication_year).nullslast(), Paper.title)
        .limit(limit)
    ).all()
    return [
        (paper, limitation_text, limitation_locator, partner_text, partner_locator)
        for paper, limitation_text, limitation_locator, partner_text, partner_locator in rows
    ]


def _attach_representative_papers(
    session: Session,
    question_id: object,
    papers: list[tuple[Paper, str | None, str | None, str | None, str | None]],
    opportunity: ResearchOpportunity,
) -> None:
    for index, (paper, limitation_text, limitation_locator, partner_text, partner_locator) in enumerate(papers):
        literature_tier = "core" if index < 3 else "reading" if index < 6 else "candidate"
        relation = "context" if index < 3 else "supports"
        relationship_note = (
            f"Imported from opportunity '{opportunity.slug}'. "
            f"Limitation evidence: {_truncate(limitation_text or '', max_chars=180)} "
            f"[{limitation_locator or 'locator unavailable'}]. "
            f"Partner evidence: {_truncate(partner_text or '', max_chars=180)} "
            f"[{partner_locator or 'locator unavailable'}]."
        )
        session.add(
            ResearchQuestionPaper(
                research_question_id=question_id,
                paper_id=paper.id,
                relation=relation,
                literature_tier=literature_tier,
                relationship_note=relationship_note,
            )
        )
        if session.scalar(select(ReadingQueue).where(ReadingQueue.paper_id == paper.id)) is None:
            session.add(ReadingQueue(paper_id=paper.id, status="unread", priority=max(40, 90 - index * 5)))


def _create_question_direction(
    session: Session,
    question_id: object,
    opportunity: ResearchOpportunity,
    limitation: str | None,
    partner_type: str | None,
    partner_label: str | None,
) -> ResearchDirection:
    direction_title = _question_title(opportunity, limitation, partner_label)
    direction = ResearchDirection(
        research_question_id=question_id,
        title=direction_title,
        rationale=opportunity.rationale,
        status="selected",
        evidence_status="insufficient_evidence",
        dimensions={
            "novelty": 4,
            "theory_fit": 3,
            "data_feasibility": 4 if partner_type == "dataset" else 3,
            "method_feasibility": 4 if partner_type == "method" else 3,
            "scope_fit": 4,
            "personal_interest": 3,
        },
        evidence_for=opportunity.signals.get("limitation_evidence") if opportunity.signals else None,
        evidence_against="No claim of a true gap yet; run the falsification search first.",
        next_test=_falsification_query(limitation, partner_label),
        data_note=partner_label if partner_type == "dataset" else None,
        method_note=partner_label if partner_type == "method" else opportunity.recommended_method,
    )
    session.add(direction)
    return direction


def _create_question_design(
    session: Session,
    question_id: object,
    selected_direction_id: object,
    limitation: str | None,
    partner_type: str | None,
    partner_label: str | None,
) -> None:
    session.add(
        ResearchDesign(
            research_question_id=question_id,
            selected_direction_id=selected_direction_id,
            focal_constructs=limitation,
            data_sources=partner_label if partner_type == "dataset" else None,
            methodology=partner_label if partner_type == "method" else None,
            analysis_plan=partner_label if partner_type == "evaluation_metric" else None,
            expected_contribution=(
                "Convert an observed recurring limitation into a verifiable research design "
                "with explicit evidence, boundary, and falsification checks."
            ),
            feasibility_notes="Pre-filled from signal-grounded opportunity; refine after reading linked core papers.",
            status="developing",
        )
    )


def _create_gap_canvas(
    session: Session,
    question_id: object,
    opportunity: ResearchOpportunity,
    primary_query: str,
    falsification_query: str,
) -> None:
    session.add(
        GapAnalysis(
            research_question_id=question_id,
            search_strategy=(
                f"Start with: {primary_query}\n"
                f"Then falsify with: {falsification_query}\n"
                "Use fast abstract search first, then deep full-text search only after narrowing the question."
            ),
            inclusion_criteria=(
                "AI × MOT studies that explicitly discuss the limitation and provide method, data, "
                "or evaluation evidence relevant to the chosen design."
            ),
            exclusion_criteria="Pure tool-use papers, opinion-only pieces, and studies without inspectable evidence.",
            research_clusters=opportunity.signals.get("partner_label") if opportunity.signals else opportunity.title,
            agreements=opportunity.signals.get("partner_evidence") if opportunity.signals else None,
            conflicts=None,
            under_studied_contexts=opportunity.signals.get("limitation") if opportunity.signals else None,
            gap_candidates=opportunity.title,
            falsifiability_notes="This canvas is a starting point; the first task is to disprove the apparent gap.",
            follow_up_questions="Which papers already solve this limitation, and under what boundary conditions?",
            theoretical_lenses=None,
            candidate_data_methods=opportunity.recommended_method,
            status="draft",
        )
    )


def _create_import_note(
    session: Session,
    question_id: object,
    opportunity: ResearchOpportunity,
    papers: list[tuple[Paper, str | None, str | None, str | None, str | None]],
    *,
    saved_searches: list[SavedSearch],
) -> None:
    paper_lines = [
        f"- {paper.publication_year or 'n.d.'} · {paper.title}"
        for paper, *_ in papers[:8]
    ]
    search_lines = [f"- {search.name}: `{search.query_text}`" for search in saved_searches]
    markdown = "\n".join(
        [
            f"# Imported from opportunity: {opportunity.title}",
            "",
            "## How to use this workspace",
            "1. Read the linked core papers first.",
            "2. Run the falsification search before calling this a research gap.",
            "3. Promote papers to foundation/core only after checking source locators.",
            "4. Turn the design notes into hypotheses after evidence review.",
            "",
            "## Saved searches",
            *search_lines,
            "",
            "## Seed papers",
            *(paper_lines or ["- No source-located seed papers were available for this opportunity yet."]),
        ]
    )
    session.add(ResearchQuestionNote(research_question_id=question_id, note_markdown=markdown))


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
