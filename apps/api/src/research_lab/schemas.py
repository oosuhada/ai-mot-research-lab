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


class SearchResponseItem(PaperSummary):
    lexical_rank: int | None = None
    semantic_rank: int | None = None
    fused_score: float


class SearchResponse(BaseModel):
    query: str
    mode: str
    total: int
    items: list[SearchResponseItem]


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
    axes: list[LandscapeAxis]
    years: list[LandscapeYear]
    top_authors: list[LandscapeLeader]
    top_institutions: list[LandscapeLeader]
    top_venues: list[LandscapeLeader]
    oa_papers: int


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
    paper_ids: list[uuid.UUID] = Field(min_length=2, max_length=8)


class EvidenceLinkResponse(BaseModel):
    paper_id: uuid.UUID
    paper_title: str
    doi: str | None = None
    primary_url: str | None = None
    relation: str
    source_locator: str | None = None


class ComparisonCellResponse(BaseModel):
    id: uuid.UUID
    paper_id: uuid.UUID
    field_name: str
    value_text: str | None
    support_status: str
    claim_kind: str
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


class GapAnalysisCreate(BaseModel):
    topic: str = Field(min_length=3, max_length=1000)
    title: str | None = Field(default=None, max_length=500)
    retrieval_limit: int = Field(default=20, ge=5, le=50)


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

