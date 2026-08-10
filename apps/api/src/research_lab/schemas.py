from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


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

    def validate_grounding(self) -> None:
        if self.support_status != "insufficient_evidence" and not self.evidence:
            raise ValueError("Supported, mixed, or contradicted claims require evidence links")


class ReadingQueueUpdate(BaseModel):
    status: str
    priority: int = 0


class PaperNoteCreate(BaseModel):
    note_markdown: str = Field(min_length=1)
    source_locator: str | None = None


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


class LandscapeResponse(BaseModel):
    total_papers: int
    axes: list[LandscapeAxis]
    years: list[LandscapeYear]


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

