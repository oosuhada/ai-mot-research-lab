from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from research_lab.models import (
    ComparisonSet,
    GapAnalysis,
    Paper,
    ResearchQuestion,
    ResearchQuestionComparisonSet,
    ResearchQuestionNote,
    ResearchQuestionPaper,
    ResearchQuestionSavedSearch,
    SavedSearch,
)
from research_lab.schemas import (
    ResearchQuestionComparisonResponse,
    ResearchQuestionCreate,
    ResearchQuestionGapResponse,
    ResearchQuestionNoteResponse,
    ResearchQuestionPaperResponse,
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
        select(Paper, ResearchQuestionPaper.relation)
        .join(ResearchQuestionPaper, ResearchQuestionPaper.paper_id == Paper.id)
        .where(ResearchQuestionPaper.research_question_id == question_id)
        .order_by(Paper.publication_year.desc().nullslast(), Paper.title)
    ).all()
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
                relation=relation,
            )
            for paper, relation in paper_rows
        ],
        saved_searches=[
            ResearchQuestionSavedSearchResponse(id=row.id, name=row.name, query_text=row.query_text)
            for row in saved_rows
        ],
        comparison_sets=[ResearchQuestionComparisonResponse(id=row.id, name=row.name) for row in comparison_rows],
        gap_analyses=[
            ResearchQuestionGapResponse(id=row.id, status=row.status, gap_candidates=row.gap_candidates)
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
        created_at=question.created_at,
        updated_at=question.updated_at,
    )


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
