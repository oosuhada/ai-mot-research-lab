from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from research_lab.chat import answer_chat
from research_lab.citation_graph import get_snowball_neighbors
from research_lab.comparison import (
    create_comparison_set,
    export_comparison,
    get_comparison_set,
    list_comparison_sets,
    update_comparison_cell,
)
from research_lab.config import get_settings
from research_lab.corpus_intelligence import (
    get_corpus_coverage,
    get_full_text_queue,
    list_research_opportunities,
    list_whats_new,
)
from research_lab.db import get_db
from research_lab.embedding_selection import choose_search_embedding_provider
from research_lab.gap_analysis import create_gap_analysis, get_gap_analysis, update_gap_analysis
from research_lab.library import (
    add_note,
    assign_tag,
    browse_papers,
    create_saved_search,
    delete_note,
    get_landscape,
    get_paper_detail,
    list_saved_searches,
    remove_tag,
    set_reading_state,
)
from research_lab.observability import get_retrieval_health
from research_lab.pdf_pipeline import PdfEvidenceService
from research_lab.patent_imports import PatentImportService
from research_lab.reranking import build_reranker
from research_lab.research_questions import (
    add_question_note,
    attach_question_comparison,
    attach_question_paper,
    attach_question_saved_search,
    create_research_question,
    get_research_question,
    list_research_questions,
    recommend_question_papers,
    update_research_question,
)
from research_lab.research_workflow import (
    build_research_proposal,
    create_research_direction,
    get_paper_research_card,
    persist_paper_research_card,
    update_paper_research_card,
    update_question_paper,
    update_research_direction,
    upsert_research_design,
)
from research_lab.retrieval import HybridRetrievalService, SearchFilters
from research_lab.schemas import (
    BrowseResponse,
    ChatRequest,
    ChatResponse,
    CitationSnowballResponse,
    ComparisonCellUpdate,
    ComparisonSetCreate,
    ComparisonSetResponse,
    ComparisonSetSummary,
    CorpusCoverageResponse,
    FullTextQueueResponse,
    GapAnalysisCreate,
    GapAnalysisResponse,
    GapAnalysisUpdate,
    LandscapeResponse,
    MetadataImportRequest,
    MetadataImportResponse,
    PaperDetail,
    PaperNoteCreate,
    PaperNoteResponse,
    PaperResearchCardResponse,
    PaperResearchCardUpdate,
    PatentImportRequest,
    PatentImportResponse,
    PdfIngestResponse,
    ReadingQueueState,
    ReadingQueueUpdate,
    ResearchDesignResponse,
    ResearchDesignUpdate,
    ResearchDirectionCreate,
    ResearchDirectionResponse,
    ResearchDirectionUpdate,
    ResearchOpportunitiesResponse,
    ResearchProposalResponse,
    ResearchQuestionCreate,
    ResearchQuestionLinkRequest,
    ResearchQuestionNoteCreate,
    ResearchQuestionPaperUpdate,
    ResearchQuestionRecommendation,
    ResearchQuestionResponse,
    ResearchQuestionUpdate,
    RetrievalHealthResponse,
    SavedSearchCreate,
    SavedSearchResponse,
    SearchResponse,
    SearchResponseItem,
    TagAssign,
    TagResponse,
    WhatsNewResponse,
)
from research_lab.user_imports import UserImportService

router = APIRouter(prefix="/api/v1")


@router.get("/landscape", response_model=LandscapeResponse, tags=["landscape"])
def landscape(db: Annotated[Session, Depends(get_db)]) -> LandscapeResponse:
    return get_landscape(db)


@router.get("/corpus/coverage", response_model=CorpusCoverageResponse, tags=["landscape", "corpus"])
def corpus_coverage(db: Annotated[Session, Depends(get_db)]) -> CorpusCoverageResponse:
    return get_corpus_coverage(db)


@router.get("/corpus/full-text-queue", response_model=FullTextQueueResponse, tags=["corpus"])
def full_text_queue(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> FullTextQueueResponse:
    return get_full_text_queue(db, limit=limit)


@router.get("/whats-new", response_model=WhatsNewResponse, tags=["discovery"])
def whats_new(
    db: Annotated[Session, Depends(get_db)],
    days: Annotated[int, Query(ge=1, le=90)] = 7,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> WhatsNewResponse:
    return list_whats_new(db, days=days, limit=limit)


@router.get(
    "/research-opportunities",
    response_model=ResearchOpportunitiesResponse,
    tags=["gap-analysis", "discovery"],
)
def research_opportunities(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=50)] = 12,
) -> ResearchOpportunitiesResponse:
    return list_research_opportunities(db, limit=limit)


@router.get("/retrieval/health", response_model=RetrievalHealthResponse, tags=["system", "search"])
def retrieval_health(db: Annotated[Session, Depends(get_db)]) -> RetrievalHealthResponse:
    return get_retrieval_health(db, get_settings())


@router.get("/search", response_model=SearchResponse, tags=["search"])
def search_papers(
    db: Annotated[Session, Depends(get_db)],
    q: Annotated[str, Query(min_length=2, max_length=500)],
    mode: Literal["lexical", "vector", "hybrid"] = "hybrid",
    semantic_provider: Literal["auto", "local_hash", "fastembed"] = "auto",
    rerank: Literal["none", "fastembed"] = "none",
    scope: Literal["metadata", "abstract", "full_text", "all"] = "all",
    sort: Literal["relevance", "newest", "citation_count", "reading_priority"] = "relevance",
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
    year_from: int | None = None,
    year_to: int | None = None,
    axis: str | None = None,
    work_type: str | None = None,
    venue: str | None = None,
    author: str | None = None,
    methodology: str | None = None,
    is_oa: bool | None = None,
    reading_status: str | None = None,
    tag: str | None = None,
) -> SearchResponse:
    try:
        selection = choose_search_embedding_provider(db, get_settings(), semantic_provider)
        embedding_provider = selection.provider
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    service = HybridRetrievalService(db, embedding_provider)
    candidate_cap = 100
    rows = service.search(
        q,
        mode=mode,
        scope=scope,
        sort=sort,
        limit=candidate_cap,
        filters=SearchFilters(
            year_from=year_from,
            year_to=year_to,
            axis=axis,
            work_type=work_type,
            venue=venue,
            author=author,
            methodology=methodology,
            is_oa=is_oa,
            reading_status=reading_status,
            tag=tag,
        ),
    )
    try:
        reranker = build_reranker(get_settings(), rerank)
        rows = reranker.rerank(q, rows, limit=candidate_cap) if reranker is not None else rows
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    total = len(rows)
    page_rows = rows[offset : offset + limit]

    return SearchResponse(
        query=q,
        mode=mode,
        semantic_provider=embedding_provider.name,
        semantic_provider_requested=semantic_provider,
        semantic_provider_reason=selection.reason,
        reranker=reranker.name if reranker is not None else "none",
        scope=scope,
        sort=sort,
        total=total,
        offset=offset,
        limit=limit,
        has_more=offset + len(page_rows) < total,
        candidate_cap=candidate_cap,
        total_is_capped=total >= candidate_cap,
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
                venue_name=row.venue_name,
                oa_status=row.oa_status,
                is_oa=row.is_oa,
                primary_url=row.primary_url,
                pdf_url=row.pdf_url,
                license=row.license,
                lexical_rank=row.lexical_rank,
                semantic_rank=row.semantic_rank,
                fused_score=row.fused_score,
                rerank_score=row.rerank_score,
                matched_source=row.matched_source,
                matched_locator=row.matched_locator,
                matched_excerpt=row.matched_excerpt,
                citation_count=row.citation_count,
                reading_priority=row.reading_priority,
            )
            for row in page_rows
        ],
    )


@router.get("/papers", response_model=BrowseResponse, tags=["library"])
def browse_all_papers(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    axis: str | None = None,
    work_type: str | None = None,
    venue: str | None = None,
    author: str | None = None,
    methodology: str | None = None,
    is_oa: bool | None = None,
    reading_status: str | None = None,
    tag: str | None = None,
) -> BrowseResponse:
    return browse_papers(
        db,
        limit=limit,
        cursor=cursor,
        filters=SearchFilters(
            year_from=year_from,
            year_to=year_to,
            axis=axis,
            work_type=work_type,
            venue=venue,
            author=author,
            methodology=methodology,
            is_oa=is_oa,
            reading_status=reading_status,
            tag=tag,
        ),
    )


@router.get("/papers/{paper_id}", response_model=PaperDetail, tags=["library"])
def paper_detail(
    paper_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> PaperDetail:
    return get_paper_detail(db, paper_id)


@router.get(
    "/papers/{paper_id}/citations/snowball",
    response_model=CitationSnowballResponse,
    tags=["library"],
)
def paper_citation_snowball(
    paper_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    backward_limit: Annotated[int, Query(ge=1, le=100)] = 20,
    forward_limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> CitationSnowballResponse:
    return get_snowball_neighbors(
        db,
        paper_id,
        backward_limit=backward_limit,
        forward_limit=forward_limit,
    )


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


@router.get(
    "/papers/{paper_id}/research-card",
    response_model=PaperResearchCardResponse,
    tags=["library", "research-workflow"],
)
def paper_research_card(
    paper_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> PaperResearchCardResponse:
    return get_paper_research_card(db, paper_id)


@router.post(
    "/papers/{paper_id}/research-card",
    response_model=PaperResearchCardResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["library", "research-workflow"],
)
def save_paper_research_card(
    paper_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> PaperResearchCardResponse:
    return persist_paper_research_card(db, paper_id)


@router.patch(
    "/papers/{paper_id}/research-card",
    response_model=PaperResearchCardResponse,
    tags=["library", "research-workflow"],
)
def edit_paper_research_card(
    paper_id: uuid.UUID,
    payload: PaperResearchCardUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> PaperResearchCardResponse:
    return update_paper_research_card(db, paper_id, payload)


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
    "/research-questions",
    response_model=ResearchQuestionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["research-questions"],
)
def create_question(
    payload: ResearchQuestionCreate,
    db: Annotated[Session, Depends(get_db)],
) -> ResearchQuestionResponse:
    return create_research_question(db, payload)


@router.get("/research-questions", response_model=list[ResearchQuestionResponse], tags=["research-questions"])
def research_questions(db: Annotated[Session, Depends(get_db)]) -> list[ResearchQuestionResponse]:
    return list_research_questions(db)


@router.get(
    "/research-questions/{question_id}",
    response_model=ResearchQuestionResponse,
    tags=["research-questions"],
)
def research_question_detail(
    question_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> ResearchQuestionResponse:
    return get_research_question(db, question_id)


@router.get(
    "/research-questions/{question_id}/recommendations",
    response_model=list[ResearchQuestionRecommendation],
    tags=["research-questions"],
)
def research_question_recommendations(
    question_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=50)] = 12,
) -> list[ResearchQuestionRecommendation]:
    return recommend_question_papers(db, question_id, limit=limit)


@router.patch(
    "/research-questions/{question_id}",
    response_model=ResearchQuestionResponse,
    tags=["research-questions"],
)
def edit_research_question(
    question_id: uuid.UUID,
    payload: ResearchQuestionUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> ResearchQuestionResponse:
    return update_research_question(db, question_id, payload)


@router.post(
    "/research-questions/{question_id}/papers",
    response_model=ResearchQuestionResponse,
    tags=["research-questions"],
)
def link_question_paper(
    question_id: uuid.UUID,
    payload: ResearchQuestionLinkRequest,
    db: Annotated[Session, Depends(get_db)],
) -> ResearchQuestionResponse:
    return attach_question_paper(db, question_id, payload.entity_id)


@router.patch(
    "/research-questions/{question_id}/papers/{paper_id}",
    response_model=ResearchQuestionResponse,
    tags=["research-questions", "research-workflow"],
)
def edit_question_paper(
    question_id: uuid.UUID,
    paper_id: uuid.UUID,
    payload: ResearchQuestionPaperUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> ResearchQuestionResponse:
    update_question_paper(db, question_id, paper_id, payload)
    return get_research_question(db, question_id)


@router.post(
    "/research-questions/{question_id}/saved-searches",
    response_model=ResearchQuestionResponse,
    tags=["research-questions"],
)
def link_question_search(
    question_id: uuid.UUID,
    payload: ResearchQuestionLinkRequest,
    db: Annotated[Session, Depends(get_db)],
) -> ResearchQuestionResponse:
    return attach_question_saved_search(db, question_id, payload.entity_id)


@router.post(
    "/research-questions/{question_id}/comparison-sets",
    response_model=ResearchQuestionResponse,
    tags=["research-questions"],
)
def link_question_comparison(
    question_id: uuid.UUID,
    payload: ResearchQuestionLinkRequest,
    db: Annotated[Session, Depends(get_db)],
) -> ResearchQuestionResponse:
    return attach_question_comparison(db, question_id, payload.entity_id)


@router.post(
    "/research-questions/{question_id}/notes",
    response_model=ResearchQuestionResponse,
    tags=["research-questions"],
)
def add_research_question_note(
    question_id: uuid.UUID,
    payload: ResearchQuestionNoteCreate,
    db: Annotated[Session, Depends(get_db)],
) -> ResearchQuestionResponse:
    return add_question_note(db, question_id, payload.note_markdown)


@router.post(
    "/research-questions/{question_id}/directions",
    response_model=ResearchDirectionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["research-questions", "research-workflow"],
)
def add_research_direction(
    question_id: uuid.UUID,
    payload: ResearchDirectionCreate,
    db: Annotated[Session, Depends(get_db)],
) -> ResearchDirectionResponse:
    return create_research_direction(db, question_id, payload)


@router.patch(
    "/research-questions/{question_id}/directions/{direction_id}",
    response_model=ResearchDirectionResponse,
    tags=["research-questions", "research-workflow"],
)
def edit_research_direction(
    question_id: uuid.UUID,
    direction_id: uuid.UUID,
    payload: ResearchDirectionUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> ResearchDirectionResponse:
    return update_research_direction(db, question_id, direction_id, payload)


@router.put(
    "/research-questions/{question_id}/design",
    response_model=ResearchDesignResponse,
    tags=["research-questions", "research-workflow"],
)
def save_research_design(
    question_id: uuid.UUID,
    payload: ResearchDesignUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> ResearchDesignResponse:
    return upsert_research_design(db, question_id, payload)


@router.get(
    "/research-questions/{question_id}/proposal",
    response_model=ResearchProposalResponse,
    tags=["research-questions", "research-workflow"],
)
def research_proposal(
    question_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> ResearchProposalResponse:
    return build_research_proposal(db, question_id)


@router.post(
    "/imports/metadata",
    response_model=MetadataImportResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["imports"],
)
def import_metadata(
    payload: MetadataImportRequest,
    db: Annotated[Session, Depends(get_db)],
) -> MetadataImportResponse:
    service = UserImportService(db, get_settings())
    result = service.import_text(payload.format, payload.content)
    return MetadataImportResponse(
        run_id=result.run_id,
        paper_ids=result.paper_ids,
        inserted_count=result.inserted_count,
        updated_count=result.updated_count,
        error_count=result.error_count,
        errors=result.errors,
    )


@router.post(
    "/imports/patents",
    response_model=PatentImportResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["imports", "patents"],
)
def import_patents(
    payload: PatentImportRequest,
    db: Annotated[Session, Depends(get_db)],
) -> PatentImportResponse:
    service = PatentImportService(db)
    result = service.import_wips_csv(payload.content)
    return PatentImportResponse(
        run_id=result.run_id,
        patent_ids=result.patent_ids,
        inserted_count=result.inserted_count,
        updated_count=result.updated_count,
        error_count=result.error_count,
        errors=result.errors,
    )


@router.post(
    "/papers/{paper_id}/pdf",
    response_model=PdfIngestResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["imports"],
)
async def import_private_pdf(
    paper_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    file: Annotated[UploadFile, File()],
    rights_confirmed: Annotated[bool, Form()],
) -> PdfIngestResponse:
    if not rights_confirmed:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=422,
            detail="Confirm that you own the file or have permission to process it privately",
        )
    data = await file.read()
    service = PdfEvidenceService(db, get_settings())
    result = service.ingest(paper_id, file.filename or "upload.pdf", data)
    return PdfIngestResponse(
        run_id=result.run_id,
        paper_id=result.paper_id,
        version_id=result.version_id,
        chunk_count=result.chunk_count,
        page_count=result.page_count,
        extraction_status=result.extraction_status,
        private_blob_id=result.private_blob_id,
    )


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
    "/comparison-sets",
    response_model=list[ComparisonSetSummary],
    tags=["comparison"],
)
def comparison_list(
    db: Annotated[Session, Depends(get_db)],
) -> list[ComparisonSetSummary]:
    return list_comparison_sets(db)


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


@router.patch(
    "/comparison-sets/{comparison_set_id}/cells/{cell_id}",
    response_model=ComparisonSetResponse,
    tags=["comparison"],
)
def edit_comparison_cell(
    comparison_set_id: uuid.UUID,
    cell_id: uuid.UUID,
    payload: ComparisonCellUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> ComparisonSetResponse:
    return update_comparison_cell(db, comparison_set_id, cell_id, payload)


@router.get("/comparison-sets/{comparison_set_id}/export", tags=["comparison"])
def comparison_export(
    comparison_set_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    format: Literal["markdown", "csv"] = "markdown",
) -> Response:
    content = export_comparison(db, comparison_set_id, format)
    media_type = "text/markdown; charset=utf-8" if format == "markdown" else "text/csv; charset=utf-8"
    extension = "md" if format == "markdown" else "csv"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="comparison-{comparison_set_id}.{extension}"'},
    )


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


@router.post("/chat", response_model=ChatResponse, tags=["chat"])
def evidence_chat(
    payload: ChatRequest,
    db: Annotated[Session, Depends(get_db)],
) -> ChatResponse:
    return answer_chat(db, payload)
