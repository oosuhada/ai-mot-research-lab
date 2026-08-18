from __future__ import annotations

import re
import uuid
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from research_lab.comparison import COMPARISON_FIELDS, extract_comparison_fields
from research_lab.models import (
    GapAnalysis,
    Paper,
    PaperChunk,
    PaperResearchCard,
    ResearchDesign,
    ResearchDirection,
    ResearchQuestion,
    ResearchQuestionComparisonSet,
    ResearchQuestionPaper,
)
from research_lab.schemas import (
    PaperResearchCardResponse,
    PaperResearchCardUpdate,
    ProposalSectionResponse,
    ResearchCardField,
    ResearchDesignResponse,
    ResearchDesignUpdate,
    ResearchDirectionCreate,
    ResearchDirectionResponse,
    ResearchDirectionUpdate,
    ResearchProposalResponse,
    ResearchQuestionPaperUpdate,
    ResearchSynthesisResponse,
    ResearchWorkflowResponse,
)

RESEARCH_CARD_VERSION = "research_card_v1"
RESEARCH_CARD_FIELDS = (
    "one_line_summary",
    *COMPARISON_FIELDS,
    "analysis_technique",
)
DIMENSION_KEYS = (
    "novelty",
    "theory_fit",
    "data_feasibility",
    "method_feasibility",
    "scope_fit",
    "personal_interest",
)


def get_paper_research_card(
    session: Session,
    paper_id: uuid.UUID,
) -> PaperResearchCardResponse:
    paper = _require_paper(session, paper_id)
    card = session.scalar(select(PaperResearchCard).where(PaperResearchCard.paper_id == paper_id))
    if card is not None:
        return _card_response(session, paper, card)
    fields, evidence_depth = _extract_candidate_fields(session, paper)
    return PaperResearchCardResponse(
        paper_id=paper.id,
        persisted=False,
        status="candidate",
        extraction_version=RESEARCH_CARD_VERSION,
        evidence_depth=evidence_depth,
        fields=fields,
    )


def persist_paper_research_card(
    session: Session,
    paper_id: uuid.UUID,
) -> PaperResearchCardResponse:
    paper = _require_paper(session, paper_id)
    card = session.scalar(select(PaperResearchCard).where(PaperResearchCard.paper_id == paper_id))
    if card is None:
        fields, _ = _extract_candidate_fields(session, paper)
        card = PaperResearchCard(
            paper_id=paper.id,
            status="candidate",
            extraction_version=RESEARCH_CARD_VERSION,
            fields={key: value.model_dump(mode="json") for key, value in fields.items()},
        )
        session.add(card)
        session.commit()
        session.refresh(card)
    return _card_response(session, paper, card)


def update_paper_research_card(
    session: Session,
    paper_id: uuid.UUID,
    payload: PaperResearchCardUpdate,
) -> PaperResearchCardResponse:
    paper = _require_paper(session, paper_id)
    card = session.scalar(select(PaperResearchCard).where(PaperResearchCard.paper_id == paper_id))
    if card is None:
        persist_paper_research_card(session, paper_id)
        card = session.scalar(select(PaperResearchCard).where(PaperResearchCard.paper_id == paper_id))
    if card is None:
        raise RuntimeError("Research card persistence failed")

    changes = payload.model_dump(exclude_unset=True)
    raw_field_updates = changes.pop("fields", None)
    if raw_field_updates is not None:
        fields = dict(card.fields or {})
        for field_name, raw_update in raw_field_updates.items():
            if field_name not in RESEARCH_CARD_FIELDS:
                raise HTTPException(status_code=422, detail=f"Unknown research-card field: {field_name}")
            update = raw_update if isinstance(raw_update, dict) else raw_update.model_dump()
            value_text = _clean_optional_text(update.get("value_text"))
            source_locator = _clean_optional_text(update.get("source_locator"))
            existing = fields.get(field_name)
            if isinstance(existing, dict):
                existing_value = _clean_optional_text(existing.get("value_text"))
                existing_locator = _clean_optional_text(existing.get("source_locator"))
                if value_text == existing_value and source_locator == existing_locator:
                    continue
            fields[field_name] = ResearchCardField(
                value_text=value_text,
                origin="user_note",
                support_status="supported" if value_text and source_locator else "insufficient_evidence",
                source_locator=source_locator,
                chunk_id=None,
            ).model_dump(mode="json")
        card.fields = fields

    for field_name in ("important_quotes", "my_interpretation", "questions_raised", "review_notes"):
        if field_name in changes:
            setattr(card, field_name, _clean_optional_text(changes[field_name]))

    if "status" in changes and changes["status"] is not None:
        card.status = str(changes["status"])
        card.reviewed_at = datetime.now(UTC) if card.status == "reviewed" else None

    session.commit()
    session.refresh(card)
    return _card_response(session, paper, card)


def update_question_paper(
    session: Session,
    question_id: uuid.UUID,
    paper_id: uuid.UUID,
    payload: ResearchQuestionPaperUpdate,
) -> None:
    link = session.get(
        ResearchQuestionPaper,
        {"research_question_id": question_id, "paper_id": paper_id},
    )
    if link is None:
        raise HTTPException(status_code=404, detail="Paper is not linked to this research question")
    for field_name, value in payload.model_dump(exclude_unset=True).items():
        if field_name == "relationship_note":
            value = _clean_optional_text(value)
        if value is not None or field_name == "relationship_note":
            setattr(link, field_name, value)
    session.commit()


def create_research_direction(
    session: Session,
    question_id: uuid.UUID,
    payload: ResearchDirectionCreate,
) -> ResearchDirectionResponse:
    _require_question(session, question_id)
    if payload.status == "selected":
        _clear_selected_directions(session, question_id)
    row = ResearchDirection(
        research_question_id=question_id,
        **payload.model_dump(),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _direction_response(row)


def update_research_direction(
    session: Session,
    question_id: uuid.UUID,
    direction_id: uuid.UUID,
    payload: ResearchDirectionUpdate,
) -> ResearchDirectionResponse:
    row = session.get(ResearchDirection, direction_id)
    if row is None or row.research_question_id != question_id:
        raise HTTPException(status_code=404, detail="Research direction not found")
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("status") == "selected":
        _clear_selected_directions(session, question_id, except_id=row.id)
    for field_name, value in changes.items():
        setattr(row, field_name, value)
    session.commit()
    session.refresh(row)
    return _direction_response(row)


def upsert_research_design(
    session: Session,
    question_id: uuid.UUID,
    payload: ResearchDesignUpdate,
) -> ResearchDesignResponse:
    _require_question(session, question_id)
    row = session.scalar(select(ResearchDesign).where(ResearchDesign.research_question_id == question_id))
    if row is None:
        row = ResearchDesign(research_question_id=question_id)
        session.add(row)
        session.flush()
    changes = payload.model_dump(exclude_unset=True)
    selected_direction_id = changes.get("selected_direction_id")
    if selected_direction_id is not None:
        direction = session.get(ResearchDirection, selected_direction_id)
        if direction is None or direction.research_question_id != question_id:
            raise HTTPException(status_code=422, detail="Selected direction must belong to this research question")
        _clear_selected_directions(session, question_id, except_id=direction.id)
        direction.status = "selected"
    for field_name, value in changes.items():
        if isinstance(value, str):
            value = _clean_optional_text(value)
        setattr(row, field_name, value)
    session.commit()
    session.refresh(row)
    return _design_response(row)


def build_question_workspace(
    session: Session,
    question_id: uuid.UUID,
) -> tuple[
    list[ResearchDirectionResponse],
    ResearchDesignResponse | None,
    ResearchSynthesisResponse,
    ResearchWorkflowResponse,
]:
    _require_question(session, question_id)
    links = list(
        session.scalars(select(ResearchQuestionPaper).where(ResearchQuestionPaper.research_question_id == question_id))
    )
    directions = list(
        session.scalars(
            select(ResearchDirection)
            .where(ResearchDirection.research_question_id == question_id)
            .order_by(ResearchDirection.updated_at.desc())
        )
    )
    design = session.scalar(select(ResearchDesign).where(ResearchDesign.research_question_id == question_id))
    synthesis = _build_synthesis(session, links)
    workflow = _build_workflow(session, question_id, links, directions, design, synthesis)
    return (
        [_direction_response(row) for row in directions],
        _design_response(design) if design else None,
        synthesis,
        workflow,
    )


def build_research_proposal(
    session: Session,
    question_id: uuid.UUID,
) -> ResearchProposalResponse:
    question = _require_question(session, question_id)
    directions, design, synthesis, workflow = build_question_workspace(session, question_id)
    latest_gap = session.scalar(
        select(GapAnalysis)
        .where(GapAnalysis.research_question_id == question_id)
        .order_by(GapAnalysis.updated_at.desc())
        .limit(1)
    )
    selected_direction = next((direction for direction in directions if direction.status == "selected"), None)
    linked_papers = list(
        session.execute(
            select(Paper, ResearchQuestionPaper)
            .join(ResearchQuestionPaper, ResearchQuestionPaper.paper_id == Paper.id)
            .where(
                ResearchQuestionPaper.research_question_id == question_id,
                ResearchQuestionPaper.literature_tier != "excluded",
            )
            .order_by(Paper.publication_year.desc().nullslast(), Paper.title)
        ).all()
    )

    literature_lines = []
    for paper, link in linked_papers[:30]:
        tier = link.literature_tier
        literature_lines.append(f"- [{tier}] {paper.title} ({paper.publication_year or 'year unknown'})")
    literature_content = "\n".join(literature_lines)

    sections = [
        _proposal_section(
            "problem",
            "Problem statement & motivation",
            _join_text(question.motivation, question.importance_notes),
        ),
        _proposal_section("literature", "Literature base", literature_content),
        _proposal_section(
            "synthesis",
            "What the reviewed literature currently shows",
            _synthesis_markdown(synthesis),
        ),
        _proposal_section(
            "gap",
            "Candidate gap and falsification state",
            _join_text(
                latest_gap.gap_candidates if latest_gap else None,
                latest_gap.falsifiability_notes if latest_gap else None,
            ),
        ),
        _proposal_section("rq", "Research question", question.question_text),
        _proposal_section(
            "direction",
            "Selected research direction",
            _join_text(
                selected_direction.title if selected_direction else None,
                selected_direction.rationale if selected_direction else None,
            ),
        ),
        _proposal_section("theory", "Theoretical framework", design.theoretical_framework if design else None),
        _proposal_section(
            "model",
            "Constructs, variables, and hypotheses",
            _join_text(
                design.focal_constructs if design else None,
                _label("Independent variables", design.independent_variables if design else None),
                _label("Dependent variables", design.dependent_variables if design else None),
                _label("Mediators", design.mediators if design else None),
                _label("Moderators", design.moderators if design else None),
                _label("Hypotheses", design.hypotheses if design else None),
            ),
        ),
        _proposal_section(
            "method",
            "Data and method",
            _join_text(
                _label("Unit of analysis", design.unit_of_analysis if design else None),
                _label("Context / population", design.context_population if design else None),
                _label("Data sources", design.data_sources if design else None),
                _label("Sampling", design.sampling_plan if design else None),
                _label("Methodology", design.methodology if design else None),
                _label("Analysis plan", design.analysis_plan if design else None),
            ),
        ),
        _proposal_section(
            "feasibility",
            "Feasibility and constraints",
            _join_text(
                design.feasibility_notes if design else None,
                _label("Ethics / constraints", design.ethics_constraints if design else None),
            ),
        ),
        _proposal_section(
            "contribution",
            "Expected contribution",
            design.expected_contribution if design else None,
        ),
    ]
    markdown_parts = [f"# {question.title}", "", f"**Research question:** {question.question_text}", ""]
    for section in sections:
        markdown_parts.extend([f"## {section.title}", "", section.content or "_Not yet developed._", ""])
    markdown_parts.extend(
        [
            "## References in current workspace",
            "",
            literature_content or "_No linked papers yet._",
            "",
        ]
    )
    return ResearchProposalResponse(
        research_question_id=question.id,
        readiness_pct=workflow.proposal_readiness_pct,
        sections=sections,
        markdown="\n".join(markdown_parts),
    )


def _extract_candidate_fields(
    session: Session,
    paper: Paper,
) -> tuple[dict[str, ResearchCardField], str]:
    chunks = list(
        session.scalars(
            select(PaperChunk)
            .where(PaperChunk.paper_id == paper.id)
            .order_by(PaperChunk.page_start, PaperChunk.char_start, PaperChunk.id)
        )
    )
    extracted = extract_comparison_fields(paper, chunks)
    fields: dict[str, ResearchCardField] = {}
    lead = _first_sentence(paper.abstract)
    fields["one_line_summary"] = ResearchCardField(
        value_text=lead,
        origin="paper_evidence" if lead else "system_inference",
        support_status="supported" if lead else "insufficient_evidence",
        source_locator="abstract" if lead else None,
    )
    for field_name in COMPARISON_FIELDS:
        value = extracted[field_name]
        fields[field_name] = ResearchCardField(
            value_text=(value.value_text if value.support_status == "supported" else None),
            origin="paper_evidence" if value.support_status == "supported" else "system_inference",
            support_status="supported" if value.support_status == "supported" else "insufficient_evidence",
            source_locator=value.source_locator,
            chunk_id=value.chunk_id,
        )
    fields["analysis_technique"] = _extract_analysis_technique(paper, chunks)
    evidence_depth = "full_text" if chunks else "abstract" if paper.abstract else "metadata"
    return fields, evidence_depth


def _extract_analysis_technique(paper: Paper, chunks: list[PaperChunk]) -> ResearchCardField:
    techniques = (
        "structural equation modeling",
        "structural equation model",
        "partial least squares",
        "pls-sem",
        "difference-in-differences",
        "difference in differences",
        "fixed effects",
        "random effects",
        "panel regression",
        "logistic regression",
        "linear regression",
        "thematic analysis",
        "content analysis",
        "grounded theory",
        "fsqca",
        "qualitative comparative analysis",
    )
    sources: list[tuple[str, str, uuid.UUID | None]] = [
        (chunk.text, chunk.source_locator, chunk.id) for chunk in chunks if chunk.text.strip()
    ]
    if paper.abstract:
        sources.append((paper.abstract, "abstract", None))
    for text, locator, chunk_id in sources:
        normalized = text.lower()
        found = [term for term in techniques if term in normalized]
        if found:
            return ResearchCardField(
                value_text="; ".join(dict.fromkeys(found)),
                origin="paper_evidence",
                support_status="supported",
                source_locator=locator,
                chunk_id=chunk_id,
            )
    return ResearchCardField()


def _card_response(
    session: Session,
    paper: Paper,
    card: PaperResearchCard,
) -> PaperResearchCardResponse:
    has_chunk = session.scalar(select(PaperChunk.id).where(PaperChunk.paper_id == paper.id).limit(1)) is not None
    evidence_depth = "full_text" if has_chunk else "abstract" if paper.abstract else "metadata"
    fields: dict[str, ResearchCardField] = {}
    for field_name in RESEARCH_CARD_FIELDS:
        raw = (card.fields or {}).get(field_name) or {}
        fields[field_name] = ResearchCardField.model_validate(raw)
    return PaperResearchCardResponse(
        id=card.id,
        paper_id=paper.id,
        persisted=True,
        status=card.status,
        extraction_version=card.extraction_version,
        evidence_depth=evidence_depth,
        fields=fields,
        important_quotes=card.important_quotes,
        my_interpretation=card.my_interpretation,
        questions_raised=card.questions_raised,
        review_notes=card.review_notes,
        reviewed_at=card.reviewed_at,
        created_at=card.created_at,
        updated_at=card.updated_at,
    )


def _build_synthesis(
    session: Session,
    links: list[ResearchQuestionPaper],
) -> ResearchSynthesisResponse:
    paper_ids = [link.paper_id for link in links if link.literature_tier != "excluded"]
    if not paper_ids:
        return ResearchSynthesisResponse(
            reviewed_card_count=0,
            card_count=0,
            theory_signals=[],
            methodology_signals=[],
            context_signals=[],
            limitation_leads=[],
            future_research_leads=[],
        )
    rows = list(
        session.execute(
            select(PaperResearchCard, Paper)
            .join(Paper, Paper.id == PaperResearchCard.paper_id)
            .where(PaperResearchCard.paper_id.in_(paper_ids))
        ).all()
    )
    reviewed = [(card, paper) for card, paper in rows if card.status == "reviewed"]

    theory_counter: Counter[str] = Counter()
    method_counter: Counter[str] = Counter()
    context_counter: Counter[str] = Counter()
    limitation_leads: list[dict[str, object]] = []
    future_leads: list[dict[str, object]] = []
    for card, paper in reviewed:
        fields = card.fields or {}
        for token in _split_signal(_field_text(fields, "theoretical_lens")):
            theory_counter[token] += 1
        for token in _split_signal(_field_text(fields, "methodology")):
            method_counter[token] += 1
        for token in _split_signal(_field_text(fields, "context_industry_country")):
            context_counter[token] += 1
        limitation = _field_text(fields, "limitations")
        if limitation:
            limitation_leads.append({"paper_id": str(paper.id), "paper_title": paper.title, "text": limitation})
        future = _field_text(fields, "future_research")
        if future:
            future_leads.append({"paper_id": str(paper.id), "paper_title": paper.title, "text": future})

    return ResearchSynthesisResponse(
        reviewed_card_count=len(reviewed),
        card_count=len(rows),
        theory_signals=_counter_rows(theory_counter),
        methodology_signals=_counter_rows(method_counter),
        context_signals=_counter_rows(context_counter),
        limitation_leads=limitation_leads[:8],
        future_research_leads=future_leads[:8],
    )


def _build_workflow(
    session: Session,
    question_id: uuid.UUID,
    links: list[ResearchQuestionPaper],
    directions: list[ResearchDirection],
    design: ResearchDesign | None,
    synthesis: ResearchSynthesisResponse,
) -> ResearchWorkflowResponse:
    tier_counts = Counter(link.literature_tier for link in links)
    comparison_count = int(
        session.scalar(
            select(func.count())
            .select_from(ResearchQuestionComparisonSet)
            .where(ResearchQuestionComparisonSet.research_question_id == question_id)
        )
        or 0
    )
    gap_count = len(
        list(session.scalars(select(GapAnalysis.id).where(GapAnalysis.research_question_id == question_id)))
    )
    selected_count = sum(direction.status == "selected" for direction in directions)
    design_response = _design_response(design) if design else ResearchDesignResponse()

    readiness_points = 0
    readiness_points += 10 if links else 0
    readiness_points += 10 if synthesis.reviewed_card_count >= 3 else min(synthesis.reviewed_card_count * 3, 9)
    readiness_points += 10 if tier_counts["core"] >= 3 else min(tier_counts["core"] * 3, 9)
    readiness_points += 10 if comparison_count else 0
    readiness_points += 10 if gap_count else 0
    readiness_points += 10 if directions else 0
    readiness_points += 10 if selected_count else 0
    readiness_points += round(design_response.readiness_pct * 0.3)
    proposal_readiness = min(readiness_points, 100)

    next_actions: list[str] = []
    if not links:
        next_actions.append("Link a focused candidate literature set to this question.")
    if synthesis.reviewed_card_count < 3:
        next_actions.append("Review at least three structured Research Cards before synthesizing claims.")
    if tier_counts["core"] < 3:
        next_actions.append("Promote the strongest evidence papers into the core literature tier.")
    if comparison_count == 0:
        next_actions.append("Build an evidence comparison across the core papers.")
    if gap_count == 0:
        next_actions.append("Challenge the emerging explanation with a Gap Canvas and broader search.")
    if not directions:
        next_actions.append("Record 2–4 candidate research directions and score their feasibility.")
    elif selected_count == 0:
        next_actions.append("Select one research direction after testing evidence for and against it.")
    if design_response.readiness_pct < 70:
        next_actions.append("Develop theory, constructs, data, and analysis choices in Research Design.")
    if proposal_readiness >= 70:
        next_actions.append("Review the proposal outline and resolve remaining evidence gaps before drafting prose.")

    return ResearchWorkflowResponse(
        linked_papers=len(links),
        candidate_papers=tier_counts["candidate"],
        reading_papers=tier_counts["reading"],
        core_papers=tier_counts["core"],
        foundation_papers=tier_counts["foundation"],
        reviewed_cards=synthesis.reviewed_card_count,
        comparison_sets=comparison_count,
        gap_analyses=gap_count,
        research_directions=len(directions),
        selected_directions=selected_count,
        proposal_readiness_pct=proposal_readiness,
        next_actions=next_actions[:6],
    )


def _design_response(row: ResearchDesign | None) -> ResearchDesignResponse:
    if row is None:
        return ResearchDesignResponse()
    core_fields = {
        "theoretical_framework": row.theoretical_framework,
        "focal_constructs": row.focal_constructs,
        "unit_of_analysis": row.unit_of_analysis,
        "context_population": row.context_population,
        "data_sources": row.data_sources,
        "methodology": row.methodology,
        "analysis_plan": row.analysis_plan,
        "hypotheses": row.hypotheses,
        "expected_contribution": row.expected_contribution,
    }
    missing = [key for key, value in core_fields.items() if not _clean_optional_text(value)]
    readiness = round((len(core_fields) - len(missing)) / len(core_fields) * 100)
    return ResearchDesignResponse(
        id=row.id,
        selected_direction_id=row.selected_direction_id,
        theoretical_framework=row.theoretical_framework,
        focal_constructs=row.focal_constructs,
        independent_variables=row.independent_variables,
        dependent_variables=row.dependent_variables,
        mediators=row.mediators,
        moderators=row.moderators,
        unit_of_analysis=row.unit_of_analysis,
        context_population=row.context_population,
        data_sources=row.data_sources,
        sampling_plan=row.sampling_plan,
        methodology=row.methodology,
        analysis_plan=row.analysis_plan,
        hypotheses=row.hypotheses,
        feasibility_notes=row.feasibility_notes,
        ethics_constraints=row.ethics_constraints,
        expected_contribution=row.expected_contribution,
        status=row.status,
        readiness_pct=readiness,
        missing_fields=missing,
    )


def _direction_response(row: ResearchDirection) -> ResearchDirectionResponse:
    dimensions = {key: int(value) for key, value in (row.dimensions or {}).items() if key in DIMENSION_KEYS}
    score = round(sum(dimensions.values()) / (len(dimensions) * 5) * 100, 1) if dimensions else None
    return ResearchDirectionResponse(
        id=row.id,
        title=row.title,
        rationale=row.rationale,
        status=row.status,
        evidence_status=row.evidence_status,
        dimensions=dimensions,
        score=score,
        evidence_for=row.evidence_for,
        evidence_against=row.evidence_against,
        next_test=row.next_test,
        theory_note=row.theory_note,
        data_note=row.data_note,
        method_note=row.method_note,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _clear_selected_directions(
    session: Session,
    question_id: uuid.UUID,
    *,
    except_id: uuid.UUID | None = None,
) -> None:
    rows = session.scalars(
        select(ResearchDirection).where(
            ResearchDirection.research_question_id == question_id,
            ResearchDirection.status == "selected",
        )
    )
    for row in rows:
        if row.id != except_id:
            row.status = "testing"


def _proposal_section(key: str, title: str, content: str | None) -> ProposalSectionResponse:
    cleaned = _clean_optional_text(content) or ""
    if not cleaned:
        state = "missing"
    elif len(cleaned) < 80:
        state = "partial"
    else:
        state = "ready"
    return ProposalSectionResponse(key=key, title=title, content=cleaned, evidence_state=state)


def _synthesis_markdown(synthesis: ResearchSynthesisResponse) -> str:
    lines = [
        f"Reviewed structured cards: {synthesis.reviewed_card_count}/{synthesis.card_count}.",
    ]
    if synthesis.theory_signals:
        lines.append(
            "Theory signals: " + ", ".join(f"{row['label']} ({row['count']})" for row in synthesis.theory_signals[:6])
        )
    if synthesis.methodology_signals:
        lines.append(
            "Method signals: "
            + ", ".join(f"{row['label']} ({row['count']})" for row in synthesis.methodology_signals[:6])
        )
    if synthesis.limitation_leads:
        lines.append(
            "Limitation leads:\n"
            + "\n".join(f"- {row['paper_title']}: {row['text']}" for row in synthesis.limitation_leads[:5])
        )
    return "\n\n".join(lines)


def _field_text(fields: dict[str, Any], field_name: str) -> str | None:
    raw = fields.get(field_name)
    if not isinstance(raw, dict):
        return None
    return _clean_optional_text(raw.get("value_text"))


def _split_signal(value: str | None) -> list[str]:
    if not value:
        return []
    cleaned = re.sub(r"^Evidence mentions:\s*", "", value, flags=re.IGNORECASE)
    return [token.strip() for token in re.split(r"[;|]", cleaned) if token.strip()]


def _counter_rows(counter: Counter[str]) -> list[dict[str, object]]:
    return [{"label": label, "count": count} for label, count in counter.most_common(8)]


def _first_sentence(text: str | None) -> str | None:
    if not text:
        return None
    normalized = " ".join(text.split())
    match = re.match(r"(.+?[.!?])(?:\s|$)", normalized)
    sentence = match.group(1) if match else normalized
    return sentence[:700]


def _clean_optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).strip().split())
    return text or None


def _join_text(*values: str | None) -> str:
    return "\n\n".join(value for value in (_clean_optional_text(item) for item in values) if value)


def _label(label: str, value: str | None) -> str | None:
    cleaned = _clean_optional_text(value)
    return f"**{label}:** {cleaned}" if cleaned else None


def _require_paper(session: Session, paper_id: uuid.UUID) -> Paper:
    paper = session.get(Paper, paper_id)
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    return paper


def _require_question(session: Session, question_id: uuid.UUID) -> ResearchQuestion:
    question = session.get(ResearchQuestion, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Research question not found")
    return question
