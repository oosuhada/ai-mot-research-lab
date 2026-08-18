from __future__ import annotations

import math
import uuid
from collections import defaultdict

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from research_lab.config import get_settings
from research_lab.embedding_selection import choose_search_embedding_provider
from research_lab.models import (
    Citation,
    ComparisonSet,
    GapAnalysis,
    Paper,
    PaperResearchCard,
    ReadingQueue,
    ResearchQuestion,
    ResearchQuestionComparisonSet,
    ResearchQuestionNote,
    ResearchQuestionPaper,
    ResearchQuestionSavedSearch,
    SavedSearch,
)
from research_lab.research_workflow import build_question_workspace
from research_lab.retrieval import HybridRetrievalService
from research_lab.schemas import (
    ResearchQuestionComparisonResponse,
    ResearchQuestionCreate,
    ResearchQuestionGapResponse,
    ResearchQuestionNoteResponse,
    ResearchQuestionPaperResponse,
    ResearchQuestionRecommendation,
    ResearchQuestionResponse,
    ResearchQuestionSavedSearchResponse,
    ResearchQuestionUpdate,
)


def create_research_question(session: Session, payload: ResearchQuestionCreate) -> ResearchQuestionResponse:
    question = ResearchQuestion(
        title=payload.title,
        question_text=payload.question_text,
        motivation=payload.motivation,
        scope_notes=payload.scope_notes,
        importance_notes=payload.importance_notes,
        evidence_status=payload.evidence_status,
        uncertainty_notes=payload.uncertainty_notes,
        status=payload.status,
    )
    session.add(question)
    session.flush()
    for paper_id in payload.paper_ids:
        _attach_paper(session, question.id, paper_id)
    for saved_search_id in payload.saved_search_ids:
        _attach_saved_search(session, question.id, saved_search_id)
    for comparison_set_id in payload.comparison_set_ids:
        _attach_comparison(session, question.id, comparison_set_id)
    session.commit()
    return get_research_question(session, question.id)


def list_research_questions(session: Session) -> list[ResearchQuestionResponse]:
    ids = session.scalars(select(ResearchQuestion.id).order_by(ResearchQuestion.updated_at.desc())).all()
    return [get_research_question(session, question_id) for question_id in ids]


def update_research_question(
    session: Session,
    question_id: uuid.UUID,
    payload: ResearchQuestionUpdate,
) -> ResearchQuestionResponse:
    question = _require_question(session, question_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(question, field, value)
    session.commit()
    return get_research_question(session, question_id)


def attach_question_paper(session: Session, question_id: uuid.UUID, paper_id: uuid.UUID) -> ResearchQuestionResponse:
    _require_question(session, question_id)
    _attach_paper(session, question_id, paper_id)
    session.commit()
    return get_research_question(session, question_id)


def attach_question_saved_search(
    session: Session,
    question_id: uuid.UUID,
    saved_search_id: uuid.UUID,
) -> ResearchQuestionResponse:
    _require_question(session, question_id)
    _attach_saved_search(session, question_id, saved_search_id)
    session.commit()
    return get_research_question(session, question_id)


def attach_question_comparison(
    session: Session,
    question_id: uuid.UUID,
    comparison_set_id: uuid.UUID,
) -> ResearchQuestionResponse:
    _require_question(session, question_id)
    _attach_comparison(session, question_id, comparison_set_id)
    session.commit()
    return get_research_question(session, question_id)


def add_question_note(
    session: Session,
    question_id: uuid.UUID,
    note_markdown: str,
) -> ResearchQuestionResponse:
    _require_question(session, question_id)
    session.add(ResearchQuestionNote(research_question_id=question_id, note_markdown=note_markdown))
    session.commit()
    return get_research_question(session, question_id)


def get_research_question(session: Session, question_id: uuid.UUID) -> ResearchQuestionResponse:
    question = _require_question(session, question_id)
    paper_rows = session.execute(
        select(Paper, ResearchQuestionPaper)
        .join(ResearchQuestionPaper, ResearchQuestionPaper.paper_id == Paper.id)
        .where(ResearchQuestionPaper.research_question_id == question_id)
        .order_by(Paper.publication_year.desc().nullslast(), Paper.title)
    ).all()
    card_statuses = (
        {
            paper_id: status
            for paper_id, status in session.execute(
                select(PaperResearchCard.paper_id, PaperResearchCard.status).where(
                    PaperResearchCard.paper_id.in_([paper.id for paper, _ in paper_rows])
                )
            ).all()
        }
        if paper_rows
        else {}
    )
    saved_rows = session.scalars(
        select(SavedSearch)
        .join(ResearchQuestionSavedSearch, ResearchQuestionSavedSearch.saved_search_id == SavedSearch.id)
        .where(ResearchQuestionSavedSearch.research_question_id == question_id)
        .order_by(SavedSearch.created_at.desc())
    ).all()
    comparison_rows = session.scalars(
        select(ComparisonSet)
        .join(ResearchQuestionComparisonSet, ResearchQuestionComparisonSet.comparison_set_id == ComparisonSet.id)
        .where(ResearchQuestionComparisonSet.research_question_id == question_id)
        .order_by(ComparisonSet.updated_at.desc())
    ).all()
    gaps = session.scalars(
        select(GapAnalysis)
        .where(GapAnalysis.research_question_id == question_id)
        .order_by(GapAnalysis.updated_at.desc())
    ).all()
    notes = session.scalars(
        select(ResearchQuestionNote)
        .where(ResearchQuestionNote.research_question_id == question_id)
        .order_by(ResearchQuestionNote.created_at.desc())
    ).all()
    directions, design, synthesis, workflow = build_question_workspace(session, question_id)
    return ResearchQuestionResponse(
        id=question.id,
        title=question.title,
        question_text=question.question_text,
        motivation=question.motivation,
        scope_notes=question.scope_notes,
        importance_notes=question.importance_notes,
        evidence_status=question.evidence_status,
        uncertainty_notes=question.uncertainty_notes,
        status=question.status,
        papers=[
            ResearchQuestionPaperResponse(
                id=paper.id,
                title=paper.title,
                doi=paper.doi,
                publication_year=paper.publication_year,
                relation=link.relation,
                literature_tier=link.literature_tier,
                relationship_note=link.relationship_note,
                research_card_status=card_statuses.get(paper.id),
            )
            for paper, link in paper_rows
        ],
        saved_searches=[
            ResearchQuestionSavedSearchResponse(id=row.id, name=row.name, query_text=row.query_text)
            for row in saved_rows
        ],
        comparison_sets=[ResearchQuestionComparisonResponse(id=row.id, name=row.name) for row in comparison_rows],
        gap_analyses=[
            ResearchQuestionGapResponse(
                id=row.id,
                status=row.status,
                gap_candidates=row.gap_candidates,
                search_strategy=row.search_strategy,
                created_at=row.created_at,
            )
            for row in gaps
        ],
        notes=[
            ResearchQuestionNoteResponse(
                id=row.id,
                note_markdown=row.note_markdown,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            for row in notes
        ],
        directions=directions,
        design=design,
        synthesis=synthesis,
        workflow=workflow,
        created_at=question.created_at,
        updated_at=question.updated_at,
    )


def recommend_question_papers(
    session: Session,
    question_id: uuid.UUID,
    *,
    limit: int = 12,
) -> list[ResearchQuestionRecommendation]:
    question = _require_question(session, question_id)
    attached_ids = set(
        session.scalars(
            select(ResearchQuestionPaper.paper_id).where(ResearchQuestionPaper.research_question_id == question_id)
        ).all()
    )
    query_ranks: dict[uuid.UUID, int] = {}
    backward_seeds: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    forward_seeds: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)

    settings = get_settings()
    selection = choose_search_embedding_provider(session, settings, "auto")
    provider_name = selection.provider.name
    service = HybridRetrievalService(session, selection.provider)

    try:
        search_rows = service.search(
            question.question_text,
            mode="hybrid",
            limit=max(limit * 5, 40),
        )
    except (RuntimeError, ValueError):
        fallback = choose_search_embedding_provider(session, settings, "local_hash")
        service = HybridRetrievalService(session, fallback.provider)
        provider_name = fallback.provider.name
        search_rows = service.search(
            question.question_text,
            mode="hybrid",
            limit=max(limit * 5, 40),
        )
    for rank, row in enumerate(search_rows, start=1):
        if row.id in attached_ids:
            continue
        query_ranks[row.id] = rank

    if attached_ids:
        backward_rows = session.execute(
            select(Citation.cited_paper_id, Citation.citing_paper_id).where(
                Citation.citing_paper_id.in_(attached_ids),
                Citation.cited_paper_id.is_not(None),
            )
        ).all()
        forward_rows = session.execute(
            select(Citation.citing_paper_id, Citation.cited_paper_id).where(Citation.cited_paper_id.in_(attached_ids))
        ).all()
        for candidate_id, seed_id in backward_rows:
            if candidate_id is None or candidate_id in attached_ids:
                continue
            backward_seeds[candidate_id].add(seed_id)
        for candidate_id, seed_id in forward_rows:
            if candidate_id in attached_ids:
                continue
            forward_seeds[candidate_id].add(seed_id)

    candidate_ids = set(query_ranks) | set(backward_seeds) | set(forward_seeds)
    reading_rows = (
        session.execute(
            select(ReadingQueue.paper_id, ReadingQueue.status).where(ReadingQueue.paper_id.in_(candidate_ids))
        ).all()
        if candidate_ids
        else []
    )
    reading_status = {paper_id: status for paper_id, status in reading_rows}

    scores: dict[uuid.UUID, float] = {}
    reasons: dict[uuid.UUID, list[str]] = {}
    components: dict[uuid.UUID, dict[str, float]] = {}
    for paper_id in candidate_ids:
        status = reading_status.get(paper_id)
        if status in {"read", "archived"}:
            continue
        score, score_components, score_reasons = _recommendation_score(
            query_rank=query_ranks.get(paper_id),
            backward_seed_count=len(backward_seeds.get(paper_id, set())),
            forward_seed_count=len(forward_seeds.get(paper_id, set())),
            connected_seed_count=len(backward_seeds.get(paper_id, set()) | forward_seeds.get(paper_id, set())),
            reading_status=status,
        )
        scores[paper_id] = score
        components[paper_id] = score_components
        reasons[paper_id] = score_reasons

    ordered_ids = sorted(scores, key=lambda paper_id: (-scores[paper_id], str(paper_id)))[:limit]
    papers = session.scalars(select(Paper).where(Paper.id.in_(ordered_ids))).all() if ordered_ids else []
    lookup = {paper.id: paper for paper in papers}
    return [
        ResearchQuestionRecommendation(
            id=paper_id,
            title=lookup[paper_id].title,
            doi=lookup[paper_id].doi,
            publication_year=lookup[paper_id].publication_year,
            reasons=reasons[paper_id],
            score=scores[paper_id],
            score_components=components[paper_id],
            query_rank=query_ranks.get(paper_id),
            backward_seed_count=len(backward_seeds.get(paper_id, set())),
            forward_seed_count=len(forward_seeds.get(paper_id, set())),
            reading_status=reading_status.get(paper_id),
            semantic_provider=provider_name,
        )
        for paper_id in ordered_ids
        if paper_id in lookup
    ]


def _recommendation_score(
    *,
    query_rank: int | None,
    backward_seed_count: int,
    forward_seed_count: int,
    connected_seed_count: int,
    reading_status: str | None,
) -> tuple[float, dict[str, float], list[str]]:
    query_component = 1.0 / math.log2(query_rank + 1) if query_rank is not None else 0.0
    backward_component = min(backward_seed_count * 0.18, 0.54)
    forward_component = min(forward_seed_count * 0.18, 0.54)
    bridge_component = 0.15 if connected_seed_count >= 2 else 0.0
    novelty_component = 0.10 if reading_status in {None, "unread"} else 0.0
    components = {
        "query_relevance": query_component,
        "backward_snowball": backward_component,
        "forward_snowball": forward_component,
        "multi_seed_bridge": bridge_component,
        "unread_novelty": novelty_component,
    }
    reasons: list[str] = []
    if query_rank is not None:
        reasons.append(f"query_match_rank_{query_rank}")
    if backward_seed_count:
        reasons.append(f"backward_snowball_from_{backward_seed_count}_seed")
    if forward_seed_count:
        reasons.append(f"forward_snowball_to_{forward_seed_count}_seed")
    if bridge_component:
        reasons.append("multi_seed_bridge")
    if novelty_component:
        reasons.append("unread_or_unqueued")
    return sum(components.values()), components, reasons


def _attach_paper(session: Session, question_id: uuid.UUID, paper_id: uuid.UUID) -> None:
    if session.get(Paper, paper_id) is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    key = {"research_question_id": question_id, "paper_id": paper_id}
    if session.get(ResearchQuestionPaper, key) is None:
        session.add(ResearchQuestionPaper(**key, relation="relevant"))


def _attach_saved_search(session: Session, question_id: uuid.UUID, saved_search_id: uuid.UUID) -> None:
    if session.get(SavedSearch, saved_search_id) is None:
        raise HTTPException(status_code=404, detail="Saved search not found")
    key = {"research_question_id": question_id, "saved_search_id": saved_search_id}
    if session.get(ResearchQuestionSavedSearch, key) is None:
        session.add(ResearchQuestionSavedSearch(**key))


def _attach_comparison(session: Session, question_id: uuid.UUID, comparison_set_id: uuid.UUID) -> None:
    if session.get(ComparisonSet, comparison_set_id) is None:
        raise HTTPException(status_code=404, detail="Comparison set not found")
    key = {"research_question_id": question_id, "comparison_set_id": comparison_set_id}
    if session.get(ResearchQuestionComparisonSet, key) is None:
        session.add(ResearchQuestionComparisonSet(**key))


def _require_question(session: Session, question_id: uuid.UUID) -> ResearchQuestion:
    question = session.get(ResearchQuestion, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Research question not found")
    return question
