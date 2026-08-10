from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from research_lab.comparison import create_comparison_set, get_comparison_set
from research_lab.db import get_db
from research_lab.gap_analysis import create_gap_analysis, get_gap_analysis, update_gap_analysis
from research_lab.library import (
    add_note,
    assign_tag,
    create_saved_search,
    delete_note,
    get_landscape,
    get_paper_detail,
    list_saved_searches,
    remove_tag,
    set_reading_state,
)
from research_lab.retrieval import HybridRetrievalService, SearchFilters
from research_lab.schemas import (
    ComparisonSetCreate,
    ComparisonSetResponse,
    GapAnalysisCreate,
    GapAnalysisResponse,
    GapAnalysisUpdate,
    LandscapeResponse,
    PaperDetail,
    PaperNoteCreate,
    PaperNoteResponse,
    ReadingQueueState,
    ReadingQueueUpdate,
    SavedSearchCreate,
    SavedSearchResponse,
    SearchResponse,
    SearchResponseItem,
    TagAssign,
    TagResponse,
)

router = APIRouter(prefix="/api/v1")


@router.get("/landscape", response_model=LandscapeResponse, tags=["landscape"])
def landscape(db: Annotated[Session, Depends(get_db)]) -> LandscapeResponse:
    return get_landscape(db)


@router.get("/search", response_model=SearchResponse, tags=["search"])
def search_papers(
    db: Annotated[Session, Depends(get_db)],
    q: Annotated[str, Query(min_length=2, max_length=500)],
    mode: Literal["lexical", "vector", "hybrid"] = "hybrid",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    year_from: int | None = None,
    year_to: int | None = None,
    axis: str | None = None,
    work_type: str | None = None,
    venue: str | None = None,
    author: str | None = None,
    methodology: str | None = None,
    is_oa: bool | None = None,
) -> SearchResponse:
    service = HybridRetrievalService(db)
    rows = service.search(
        q,
        mode=mode,
        limit=limit,
        filters=SearchFilters(
            year_from=year_from,
            year_to=year_to,
            axis=axis,
            work_type=work_type,
            venue=venue,
            author=author,
            methodology=methodology,
            is_oa=is_oa,
        ),
    )
    return SearchResponse(
        query=q,
        mode=mode,
        total=len(rows),
        items=[
            SearchResponseItem(
                id=row.id,
                doi=row.doi,
                openalex_id=row.openalex_id,
                title=row.title,
                abstract=row.abstract,
                publication_date=row.publication_date,
                publication_year=row.publication_year,
                work_type=row.work_type,
                oa_status=row.oa_status,
                is_oa=row.is_oa,
                primary_url=row.primary_url,
                pdf_url=row.pdf_url,
                license=row.license,
                lexical_rank=row.lexical_rank,
                semantic_rank=row.semantic_rank,
                fused_score=row.fused_score,
            )
            for row in rows
        ],
    )


@router.get("/papers/{paper_id}", response_model=PaperDetail, tags=["library"])
def paper_detail(
    paper_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> PaperDetail:
    return get_paper_detail(db, paper_id)


@router.put(
    "/papers/{paper_id}/reading",
    response_model=ReadingQueueState,
    tags=["library"],
)
def update_reading_state(
    paper_id: uuid.UUID,
    payload: ReadingQueueUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> ReadingQueueState:
    return set_reading_state(db, paper_id, status=payload.status, priority=payload.priority)


@router.post(
    "/papers/{paper_id}/notes",
    response_model=PaperNoteResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["library"],
)
def create_note(
    paper_id: uuid.UUID,
    payload: PaperNoteCreate,
    db: Annotated[Session, Depends(get_db)],
) -> PaperNoteResponse:
    return add_note(
        db,
        paper_id,
        note_markdown=payload.note_markdown,
        source_locator=payload.source_locator,
    )


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["library"])
def remove_note(note_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]) -> Response:
    delete_note(db, note_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/papers/{paper_id}/tags",
    response_model=TagResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["library"],
)
def add_tag(
    paper_id: uuid.UUID,
    payload: TagAssign,
    db: Annotated[Session, Depends(get_db)],
) -> TagResponse:
    return assign_tag(db, paper_id, payload.name)


@router.delete(
    "/papers/{paper_id}/tags/{tag_name}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["library"],
)
def delete_tag(
    paper_id: uuid.UUID,
    tag_name: str,
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    remove_tag(db, paper_id, tag_name)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/saved-searches",
    response_model=SavedSearchResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["search"],
)
def save_search(
    payload: SavedSearchCreate,
    db: Annotated[Session, Depends(get_db)],
) -> SavedSearchResponse:
    return create_saved_search(db, payload)


@router.get("/saved-searches", response_model=list[SavedSearchResponse], tags=["search"])
def saved_searches(db: Annotated[Session, Depends(get_db)]) -> list[SavedSearchResponse]:
    return list_saved_searches(db)


@router.post(
    "/comparison-sets",
    response_model=ComparisonSetResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["comparison"],
)
def create_comparison(
    payload: ComparisonSetCreate,
    db: Annotated[Session, Depends(get_db)],
) -> ComparisonSetResponse:
    return create_comparison_set(db, payload)


@router.get(
    "/comparison-sets/{comparison_set_id}",
    response_model=ComparisonSetResponse,
    tags=["comparison"],
)
def comparison_detail(
    comparison_set_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> ComparisonSetResponse:
    return get_comparison_set(db, comparison_set_id)


@router.post(
    "/gap-analyses",
    response_model=GapAnalysisResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["gap-analysis"],
)
def create_gap_canvas(
    payload: GapAnalysisCreate,
    db: Annotated[Session, Depends(get_db)],
) -> GapAnalysisResponse:
    return create_gap_analysis(db, payload)


@router.get(
    "/gap-analyses/{analysis_id}",
    response_model=GapAnalysisResponse,
    tags=["gap-analysis"],
)
def gap_canvas_detail(
    analysis_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> GapAnalysisResponse:
    return get_gap_analysis(db, analysis_id)


@router.patch(
    "/gap-analyses/{analysis_id}",
    response_model=GapAnalysisResponse,
    tags=["gap-analysis"],
)
def edit_gap_canvas(
    analysis_id: uuid.UUID,
    payload: GapAnalysisUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> GapAnalysisResponse:
    return update_gap_analysis(db, analysis_id, payload)

