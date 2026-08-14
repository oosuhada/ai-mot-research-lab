from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class HealthResponse(BaseModel):
    status: str
    service: str
    database: str


class PaperSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    doi: str | None
    openalex_id: str | None
    title: str
    abstract: str | None
    publication_date: date | None
    publication_year: int | None
    work_type: str | None
    oa_status: str | None
    is_oa: bool
    primary_url: str | None
    pdf_url: str | None
    license: str | None


class EvidenceReference(BaseModel):
    paper_id: uuid.UUID
    chunk_id: uuid.UUID | None = None
    relation: str = "supports"
    source_locator: str | None = None


class EvidenceClaimCreate(BaseModel):
    claim_text: str = Field(min_length=1)
    claim_kind: str
    support_status: str
    evidence: list[EvidenceReference] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_grounding(self) -> Self:
        if self.support_status != "insufficient_evidence" and not self.evidence:
            raise ValueError("Supported, mixed, or contradicted claims require evidence links")
        return self


class ReadingQueueUpdate(BaseModel):
    status: Literal["unread", "skimming", "reading", "read", "archived"]
    priority: int = Field(default=0, ge=0, le=100)


class PaperNoteCreate(BaseModel):
    note_markdown: str = Field(min_length=1)
    source_locator: str | None = None


class TagAssign(BaseModel):
    name: str = Field(min_length=1, max_length=128)


class AuthorSummary(BaseModel):
    id: uuid.UUID
    display_name: str
    openalex_id: str | None = None
    orcid: str | None = None


class TopicSummary(BaseModel):
    slug: str
    display_name: str
    kind: str
    assignment_source: str


class VenueSummary(BaseModel):
    id: uuid.UUID
    name: str
    publisher: str | None = None
    venue_type: str | None = None


class ReadingQueueState(BaseModel):
    status: Literal["unread", "skimming", "reading", "read", "archived"]
    priority: int


class PaperNoteResponse(BaseModel):
    id: uuid.UUID
    note_markdown: str
    source_locator: str | None
    created_at: datetime
    updated_at: datetime


class TagResponse(BaseModel):
    id: uuid.UUID
    name: str


class PaperContentProfileResponse(BaseModel):
    abstract_status: str
    full_text_status: str
    full_text_access: str
    rights_status: str
    full_text_priority: int


class PaperLocalizationResponse(BaseModel):
    locale: str
    title: str | None
    abstract: str | None
    keywords: list[str]
    status: str
    provider: str | None
    model: str | None
    translated_at: datetime | None


class PaperDetail(PaperSummary):
    language: str | None = None
    publisher: str | None = None
    retraction_status: str
    correction_status: str
    primary_source: str
    source_record_id: str
    retrieved_at: datetime
    provenance: dict[str, object]
    venue: VenueSummary | None = None
    authors: list[AuthorSummary]
    topics: list[TopicSummary]
    reading: ReadingQueueState | None = None
    notes: list[PaperNoteResponse]
    tags: list[TagResponse]
    latest_citation_count: int | None = None
    latest_citation_snapshot_at: datetime | None = None
    content_profile: PaperContentProfileResponse
    localizations: list[PaperLocalizationResponse]


class SearchResponseItem(PaperSummary):
    venue_name: str | None = None
    lexical_rank: int | None = None
    semantic_rank: int | None = None
    fused_score: float
    rerank_score: float | None = None
    matched_source: str
    matched_locator: str | None = None
    matched_excerpt: str | None = None
    citation_count: int = 0
    reading_priority: int = 0


class SearchResponse(BaseModel):
    query: str
    mode: str
    semantic_provider: str = "local_hash"
    semantic_provider_requested: str = "auto"
    semantic_provider_reason: str = ""
    reranker: str = "none"
    scope: str = "all"
    sort: str = "relevance"
    total: int
    offset: int = 0
    limit: int = 20
    has_more: bool = False
    candidate_cap: int = 100
    total_is_capped: bool = False
    items: list[SearchResponseItem]


class BrowseResponse(BaseModel):
    total: int
    offset: int = 0
    limit: int = 20
    has_previous: bool = False
    has_more: bool = False
    previous_cursor: str | None = None
    next_cursor: str | None = None
    sort: str = "imported_desc"
    items: list[SearchResponseItem]


class RetrievalProviderHealth(BaseModel):
    provider: str
    model: str
    embedding_count: int


class RetrievalHealthResponse(BaseModel):
    configured_provider: str
    auto_selected_provider: str
    auto_selection_reason: str
    fastembed_dependency_installed: bool
    database_default_hnsw_iterative_scan: str
    vector_query_hnsw_policy: str
    providers: list[RetrievalProviderHealth]
    notes: list[str]


class LandscapeAxis(BaseModel):
    slug: str
    display_name: str
    paper_count: int


class LandscapeYear(BaseModel):
    year: int
    paper_count: int


class LandscapeLeader(BaseModel):
    name: str
    paper_count: int


class LandscapeResponse(BaseModel):
    total_papers: int
    abstract_papers: int
    full_text_papers: int
    full_text_queued: int
    axes: list[LandscapeAxis]
    subaxes: list[LandscapeAxis]
    methodologies: list[LandscapeAxis]
    years: list[LandscapeYear]
    top_authors: list[LandscapeLeader]
    top_institutions: list[LandscapeLeader]
    top_venues: list[LandscapeLeader]
    oa_papers: int
    last_ingestion_at: datetime | None = None


class CorpusCoverageResponse(BaseModel):
    total_records: int
    metadata_only: int
    abstract_ready: int
    full_text_ready: int
    full_text_queued: int
    full_text_restricted: int
    translated_ko: int


class FullTextQueuePaper(BaseModel):
    paper_id: uuid.UUID
    title: str
    priority: int
    status: str
    rights_status: str
    reason_factors: dict[str, object]


class FullTextQueueResponse(BaseModel):
    pending: int
    processing: int
    completed: int
    restricted: int
    failed: int
    items: list[FullTextQueuePaper]


class WhatsNewItem(BaseModel):
    paper_id: uuid.UUID
    title: str
    abstract: str | None
    publication_date: date | None
    publication_year: int | None
    venue_name: str | None
    event_kind: str
    detected_at: datetime
    relevance_score: float
    novelty_score: float
    evidence_depth: Literal["metadata", "abstract", "full_text"]
    is_oa: bool
    topics: list[str]
    why_it_matters: str


class WhatsNewResponse(BaseModel):
    window_days: int
    generated_at: datetime
    items: list[WhatsNewItem]


class ResearchOpportunityResponse(BaseModel):
    slug: str
    title: str
    hypothesis: str
    rationale: str
    axis_slug: str | None
    evidence_status: Literal["insufficient_evidence"] = "insufficient_evidence"
    coverage_count: int
    adjacent_count: int
    signals: dict[str, object]
    recommended_method: str | None
    generated_at: datetime


class ResearchOpportunitiesResponse(BaseModel):
    generated_at: datetime
    corpus_limitations: list[str]
    items: list[ResearchOpportunityResponse]


class SavedSearchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=250)
    query_text: str = Field(min_length=1)
    filters: dict[str, object] = Field(default_factory=dict)


class SavedSearchResponse(BaseModel):
    id: uuid.UUID
    name: str
    query_text: str
    filters: dict[str, object]
    created_at: datetime


class CitationNeighbor(BaseModel):
    id: uuid.UUID
    title: str
    doi: str | None = None
    publication_year: int | None = None
    primary_url: str | None = None
    direction: Literal["backward", "forward"]
    source: str
    citation_count: int | None = None


class CitationSnowballResponse(BaseModel):
    paper_id: uuid.UUID
    paper_title: str
    backward: list[CitationNeighbor]
    forward: list[CitationNeighbor]


class ResearchQuestionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    question_text: str = Field(min_length=3, max_length=2000)
    motivation: str | None = None
    scope_notes: str | None = None
    importance_notes: str | None = None
    evidence_status: Literal["supported", "mixed", "insufficient_evidence"] = "insufficient_evidence"
    uncertainty_notes: str | None = None
    status: str = Field(default="exploring", max_length=32)
    paper_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)
    saved_search_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    comparison_set_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)


class ResearchQuestionUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    question_text: str | None = Field(default=None, min_length=3, max_length=2000)
    motivation: str | None = None
    scope_notes: str | None = None
    importance_notes: str | None = None
    evidence_status: Literal["supported", "mixed", "insufficient_evidence"] | None = None
    uncertainty_notes: str | None = None
    status: str | None = Field(default=None, max_length=32)


class ResearchQuestionLinkRequest(BaseModel):
    entity_id: uuid.UUID


class ResearchQuestionNoteCreate(BaseModel):
    note_markdown: str = Field(min_length=1, max_length=10000)


class ResearchQuestionNoteResponse(BaseModel):
    id: uuid.UUID
    note_markdown: str
    created_at: datetime
    updated_at: datetime


class ResearchQuestionPaperResponse(BaseModel):
    id: uuid.UUID
    title: str
    doi: str | None = None
    publication_year: int | None = None
    relation: str


class ResearchQuestionRecommendation(BaseModel):
    id: uuid.UUID
    title: str
    doi: str | None = None
    publication_year: int | None = None
    reasons: list[str]
    score: float
    score_components: dict[str, float]
    query_rank: int | None = None
    backward_seed_count: int = 0
    forward_seed_count: int = 0
    reading_status: str | None = None
    semantic_provider: str


class ResearchQuestionSavedSearchResponse(BaseModel):
    id: uuid.UUID
    name: str
    query_text: str


class ResearchQuestionComparisonResponse(BaseModel):
    id: uuid.UUID
    name: str


class ResearchQuestionGapResponse(BaseModel):
    id: uuid.UUID
    status: str
    gap_candidates: str | None = None
    search_strategy: str
    created_at: datetime


class ResearchQuestionResponse(BaseModel):
    id: uuid.UUID
    title: str
    question_text: str
    motivation: str | None = None
    scope_notes: str | None = None
    importance_notes: str | None = None
    evidence_status: str
    uncertainty_notes: str | None = None
    status: str
    papers: list[ResearchQuestionPaperResponse]
    saved_searches: list[ResearchQuestionSavedSearchResponse]
    comparison_sets: list[ResearchQuestionComparisonResponse]
    gap_analyses: list[ResearchQuestionGapResponse]
    notes: list[ResearchQuestionNoteResponse]
    created_at: datetime
    updated_at: datetime


class MetadataImportRequest(BaseModel):
    format: Literal["doi", "bibtex", "ris", "csv"]
    content: str = Field(min_length=1, max_length=2_000_000)


class MetadataImportResponse(BaseModel):
    run_id: uuid.UUID
    paper_ids: list[uuid.UUID]
    inserted_count: int
    updated_count: int
    error_count: int
    errors: list[str]


class PdfIngestResponse(BaseModel):
    run_id: uuid.UUID
    paper_id: uuid.UUID
    version_id: uuid.UUID
    chunk_count: int
    page_count: int
    extraction_status: str
    private_blob_id: str


class IngestionRunResponse(BaseModel):
    id: uuid.UUID
    status: str
    source: str
    fetched_count: int
    accepted_count: int
    inserted_count: int
    updated_count: int
    skipped_count: int
    error_count: int
    started_at: datetime
    finished_at: datetime | None


class ComparisonSetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=500)
    description: str | None = None
    paper_ids: list[uuid.UUID] = Field(min_length=2, max_length=6)


class ComparisonCellUpdate(BaseModel):
    value_text: str = Field(min_length=1, max_length=10000)
    evidence_chunk_id: uuid.UUID | None = None


class EvidenceLinkResponse(BaseModel):
    paper_id: uuid.UUID
    paper_title: str
    doi: str | None = None
    primary_url: str | None = None
    publication_year: int | None = None
    venue_name: str | None = None
    relation: str
    source_locator: str | None = None
    excerpt: str | None = None


class ComparisonCellResponse(BaseModel):
    id: uuid.UUID
    paper_id: uuid.UUID
    field_name: str
    value_text: str | None
    support_status: str
    claim_kind: str
    origin: str = "system_inference"
    evidence: list[EvidenceLinkResponse]


class ComparisonPaperResponse(BaseModel):
    id: uuid.UUID
    title: str
    doi: str | None = None
    publication_year: int | None = None


class ComparisonSetResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    papers: list[ComparisonPaperResponse]
    cells: list[ComparisonCellResponse]


class ComparisonSetSummary(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    paper_count: int
    updated_at: datetime


class GapAnalysisCreate(BaseModel):
    topic: str = Field(min_length=3, max_length=1000)
    title: str | None = Field(default=None, max_length=500)
    retrieval_limit: int = Field(default=20, ge=5, le=50)
    research_question_id: uuid.UUID | None = None


class GapAnalysisUpdate(BaseModel):
    research_clusters: str | None = None
    agreements: str | None = None
    conflicts: str | None = None
    under_studied_contexts: str | None = None
    gap_candidates: str | None = None
    falsifiability_notes: str | None = None
    follow_up_questions: str | None = None
    theoretical_lenses: str | None = None
    candidate_data_methods: str | None = None
    status: str | None = None


class GapEvidenceClaimResponse(BaseModel):
    id: uuid.UUID
    claim_text: str
    claim_kind: str
    support_status: str
    evidence: list[EvidenceLinkResponse]


class GapEvidenceClusterResponse(BaseModel):
    slug: str
    display_name: str
    paper_ids: list[uuid.UUID] = Field(default_factory=list)


class GapCitationCandidateResponse(BaseModel):
    paper_id: uuid.UUID
    title: str
    publication_year: int | None = None
    primary_url: str | None = None
    direction: Literal["backward", "forward", "both"]
    linked_seed_count: int = 1


class GapCitationNeighborhoodResponse(BaseModel):
    seed_paper_count: int = 0
    backward_edge_count: int = 0
    forward_edge_count: int = 0
    unique_candidate_count: int = 0
    candidates: list[GapCitationCandidateResponse] = Field(default_factory=list)


class GapCandidateResponse(BaseModel):
    hypothesis: str
    support_status: Literal["insufficient_evidence"] = "insufficient_evidence"
    evidence_for: list[str] = Field(default_factory=list)
    evidence_against: list[str] = Field(default_factory=list)
    falsifiability_note: str
    next_search_query: str
    candidate_method: str | None = None


class GapAnalysisResponse(BaseModel):
    id: uuid.UUID
    research_question_id: uuid.UUID
    research_question: str
    status: str
    search_strategy: str
    inclusion_criteria: str
    exclusion_criteria: str
    research_clusters: str | None = None
    agreements: str | None = None
    conflicts: str | None = None
    under_studied_contexts: str | None = None
    gap_candidates: str | None = None
    falsifiability_notes: str | None = None
    follow_up_questions: str | None = None
    theoretical_lenses: str | None = None
    candidate_data_methods: str | None = None
    methodology_distribution: list[LandscapeAxis] = Field(default_factory=list)
    year_distribution: list[LandscapeYear] = Field(default_factory=list)
    evidence_clusters: list[GapEvidenceClusterResponse] = Field(default_factory=list)
    citation_neighborhood: GapCitationNeighborhoodResponse = Field(
        default_factory=GapCitationNeighborhoodResponse
    )
    candidate_gap: GapCandidateResponse | None = None
    evidence_claims: list[GapEvidenceClaimResponse]


class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    scope_type: str = "corpus"
    scope_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    max_papers: int = Field(default=5, ge=1, le=10)


class ChatCitationResponse(BaseModel):
    index: int
    paper_id: uuid.UUID
    paper_title: str
    publication_year: int | None = None
    doi: str | None = None
    primary_url: str | None = None
    source_locator: str
    excerpt: str


class ChatParagraphResponse(BaseModel):
    text: str
    claim_kind: str
    support_status: str
    citation_indexes: list[int]


class ChatResponse(BaseModel):
    question: str
    scope_type: str
    provider: str
    paragraphs: list[ChatParagraphResponse]
    citations: list[ChatCitationResponse]
    structural_unsupported_claim_rate: float
    limitations: list[str]
