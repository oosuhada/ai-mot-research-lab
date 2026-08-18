from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def json_type() -> JSON:
    return JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Venue(Base, TimestampMixin):
    __tablename__ = "venues"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    openalex_id: Mapped[Optional[str]] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    issn_l: Mapped[Optional[str]] = mapped_column(String(32), index=True)
    publisher: Mapped[Optional[str]] = mapped_column(String(500))
    venue_type: Mapped[Optional[str]] = mapped_column(String(64))


class Author(Base, TimestampMixin):
    __tablename__ = "authors"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    openalex_id: Mapped[Optional[str]] = mapped_column(String(64), unique=True)
    s2_id: Mapped[Optional[str]] = mapped_column(String(64), unique=True)
    orcid: Mapped[Optional[str]] = mapped_column(String(32), unique=True)
    display_name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)


class Institution(Base, TimestampMixin):
    __tablename__ = "institutions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    openalex_id: Mapped[Optional[str]] = mapped_column(String(64), unique=True)
    ror: Mapped[Optional[str]] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    country_code: Mapped[Optional[str]] = mapped_column(String(2))
    institution_type: Mapped[Optional[str]] = mapped_column(String(64))


class Topic(Base, TimestampMixin):
    __tablename__ = "topics"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(250), nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False, default="research_axis")
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="local_taxonomy")
    source_record_id: Mapped[Optional[str]] = mapped_column(String(128))
    description: Mapped[Optional[str]] = mapped_column(Text)
    parent_topic_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("topics.id", ondelete="SET NULL"), index=True
    )


class Paper(Base, TimestampMixin):
    __tablename__ = "papers"
    __table_args__ = (
        CheckConstraint("publication_year IS NULL OR publication_year >= 1400", name="ck_papers_year"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    doi: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True)
    openalex_id: Mapped[Optional[str]] = mapped_column(String(64), unique=True, index=True)
    s2_id: Mapped[Optional[str]] = mapped_column(String(64), unique=True, index=True)
    arxiv_id: Mapped[Optional[str]] = mapped_column(String(64), unique=True, index=True)
    pubmed_id: Mapped[Optional[str]] = mapped_column(String(32), index=True)

    @property
    def pmid(self) -> str | None:
        """Alias for pubmed_id (legacy compatibility)."""
        return self.pubmed_id

    isbn: Mapped[Optional[str]] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    abstract: Mapped[Optional[str]] = mapped_column(Text)
    publication_date: Mapped[Optional[date]] = mapped_column(Date)
    publication_year: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    language: Mapped[Optional[str]] = mapped_column(String(16))
    work_type: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    venue_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("venues.id", ondelete="SET NULL"), index=True
    )
    publisher: Mapped[Optional[str]] = mapped_column(String(500))
    oa_status: Mapped[Optional[str]] = mapped_column(String(32), index=True)
    is_oa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    primary_url: Mapped[Optional[str]] = mapped_column(Text)
    pdf_url: Mapped[Optional[str]] = mapped_column(Text)
    retraction_status: Mapped[str] = mapped_column(String(32), nullable=False, default="none")
    correction_status: Mapped[str] = mapped_column(String(32), nullable=False, default="none")
    license: Mapped[Optional[str]] = mapped_column(String(255))
    primary_source: Mapped[str] = mapped_column(String(64), nullable=False)
    source_record_id: Mapped[str] = mapped_column(String(255), nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    provenance: Mapped[dict[str, Any]] = mapped_column(json_type(), nullable=False, default=dict)
    is_seminal_exception: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    venue: Mapped[Venue | None] = relationship()


class PaperAuthor(Base):
    __tablename__ = "paper_authors"
    __table_args__ = (UniqueConstraint("paper_id", "author_id", name="uq_paper_authors_pair"),)

    paper_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("authors.id", ondelete="RESTRICT"), primary_key=True
    )
    author_position: Mapped[int] = mapped_column(Integer, nullable=False)
    is_corresponding: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    raw_affiliation: Mapped[Optional[str]] = mapped_column(Text)


class AuthorInstitution(Base):
    __tablename__ = "author_institutions"

    author_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("authors.id", ondelete="CASCADE"), primary_key=True
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("institutions.id", ondelete="RESTRICT"), primary_key=True
    )
    source: Mapped[str] = mapped_column(String(64), primary_key=True)


class PaperTopic(Base):
    __tablename__ = "paper_topics"

    paper_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topics.id", ondelete="RESTRICT"), primary_key=True
    )
    score: Mapped[Optional[float]] = mapped_column(Float)
    assignment_source: Mapped[str] = mapped_column(String(64), nullable=False)


class Citation(Base, TimestampMixin):
    __tablename__ = "citations"
    __table_args__ = (
        UniqueConstraint(
            "citing_paper_id", "cited_paper_id", "cited_external_id", name="uq_citations_edge"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    citing_paper_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cited_paper_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("papers.id", ondelete="RESTRICT"), index=True
    )
    cited_external_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    is_influential: Mapped[Optional[bool]] = mapped_column(Boolean)
    context_locator: Mapped[Optional[str]] = mapped_column(Text)


class CitationSnapshot(Base):
    __tablename__ = "citation_snapshots"
    __table_args__ = (
        UniqueConstraint("paper_id", "source", "captured_at", name="uq_citation_snapshot_time"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    paper_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    citation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    oa_status: Mapped[Optional[str]] = mapped_column(String(32))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PaperVersion(Base):
    __tablename__ = "paper_versions"
    __table_args__ = (
        UniqueConstraint("paper_id", "source", "source_record_id", "payload_hash", name="uq_paper_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    paper_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("papers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    source_record_id: Mapped[str] = mapped_column(String(255), nullable=False)
    version_label: Mapped[Optional[str]] = mapped_column(String(64))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    license: Mapped[Optional[str]] = mapped_column(String(255))
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_metadata: Mapped[dict[str, Any]] = mapped_column(json_type(), nullable=False, default=dict)


class PaperEmbedding(Base):
    __tablename__ = "paper_embeddings"
    __table_args__ = (UniqueConstraint("paper_id", "provider", "model", name="uq_paper_embedding"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    paper_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False, default=384)
    embedding: Mapped[list[float]] = mapped_column(Vector(384), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PaperChunk(Base, TimestampMixin):
    __tablename__ = "paper_chunks"
    __table_args__ = (UniqueConstraint("paper_id", "text_hash", name="uq_paper_chunk_hash"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    paper_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("papers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    paper_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("paper_versions.id", ondelete="RESTRICT"), index=True
    )
    section: Mapped[Optional[str]] = mapped_column(String(500))
    page_start: Mapped[Optional[int]] = mapped_column(Integer)
    page_end: Mapped[Optional[int]] = mapped_column(Integer)
    char_start: Mapped[Optional[int]] = mapped_column(Integer)
    char_end: Mapped[Optional[int]] = mapped_column(Integer)
    source_locator: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    text_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    language: Mapped[Optional[str]] = mapped_column(String(16))
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(384))
    embedding_provider: Mapped[Optional[str]] = mapped_column(String(64))
    embedding_model: Mapped[Optional[str]] = mapped_column(String(128))


class PaperContentProfile(Base, TimestampMixin):
    __tablename__ = "paper_content_profiles"
    __table_args__ = (
        CheckConstraint(
            "abstract_status IN ('missing','available','translated')",
            name="ck_paper_content_profiles_abstract_status",
        ),
        CheckConstraint(
            "full_text_status IN ('not_requested','queued','processing','available','restricted','failed')",
            name="ck_paper_content_profiles_full_text_status",
        ),
    )

    paper_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True
    )
    abstract_status: Mapped[str] = mapped_column(String(32), nullable=False, default="missing")
    full_text_status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_requested")
    full_text_access: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    rights_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    full_text_priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    abstract_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    full_text_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class FullTextQueueItem(Base, TimestampMixin):
    __tablename__ = "full_text_queue"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','processing','completed','restricted','failed')",
            name="ck_full_text_queue_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    paper_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    reason_factors: Mapped[dict[str, Any]] = mapped_column(json_type(), nullable=False, default=dict)
    rights_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    failure_kind: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    worker_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    claimed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)


class FullTextSourceAttempt(Base):
    __tablename__ = "full_text_source_attempts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    queue_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("full_text_queue.id", ondelete="CASCADE"), nullable=False, index=True
    )
    paper_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    publisher: Mapped[Optional[str]] = mapped_column(String(500), index=True)
    source_kind: Mapped[str] = mapped_column(String(64), nullable=False, default="paper_pdf_url")
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    failure_kind: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    http_status: Mapped[Optional[int]] = mapped_column(Integer)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PaperLocalization(Base, TimestampMixin):
    __tablename__ = "paper_localizations"
    __table_args__ = (UniqueConstraint("paper_id", "locale", name="uq_paper_localizations_locale"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    paper_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    locale: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(Text)
    abstract: Mapped[Optional[str]] = mapped_column(Text)
    keywords: Mapped[list[str]] = mapped_column(json_type(), nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[Optional[str]] = mapped_column(String(64))
    model: Mapped[Optional[str]] = mapped_column(String(128))
    translated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class DailyDiscoveryEvent(Base, TimestampMixin):
    __tablename__ = "daily_discovery_events"
    __table_args__ = (
        UniqueConstraint("paper_id", "event_kind", "event_date", name="uq_daily_discovery_event"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    paper_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    novelty_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    signals: Mapped[dict[str, Any]] = mapped_column(json_type(), nullable=False, default=dict)


class ResearchOpportunity(Base, TimestampMixin):
    __tablename__ = "research_opportunities"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    axis_slug: Mapped[Optional[str]] = mapped_column(String(128))
    evidence_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="insufficient_evidence"
    )
    coverage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    adjacent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    signals: Mapped[dict[str, Any]] = mapped_column(json_type(), nullable=False, default=dict)
    recommended_method: Mapped[Optional[str]] = mapped_column(String(250))
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    taxonomy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    query_spec: Mapped[dict[str, Any]] = mapped_column(json_type(), nullable=False, default=dict)
    checkpoint: Mapped[dict[str, Any]] = mapped_column(json_type(), nullable=False, default=dict)
    fetched_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    accepted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    inserted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[Optional[str]] = mapped_column(Text)


class SavedSearch(Base, TimestampMixin):
    __tablename__ = "saved_searches"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    filters: Mapped[dict[str, Any]] = mapped_column(json_type(), nullable=False, default=dict)


class ReadingQueue(Base, TimestampMixin):
    __tablename__ = "reading_queue"
    __table_args__ = (
        CheckConstraint(
            "status IN ('unread','skimming','reading','read','archived')",
            name="ck_reading_queue_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    paper_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="unread")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class PaperNote(Base, TimestampMixin):
    __tablename__ = "paper_notes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    paper_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    note_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    source_locator: Mapped[Optional[str]] = mapped_column(Text)


class Tag(Base, TimestampMixin):
    __tablename__ = "tags"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)


class PaperTag(Base):
    __tablename__ = "paper_tags"

    paper_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )


class ResearchQuestion(Base, TimestampMixin):
    __tablename__ = "research_questions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    motivation: Mapped[Optional[str]] = mapped_column(Text)
    scope_notes: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="exploring")
    importance_notes: Mapped[Optional[str]] = mapped_column(Text)
    evidence_status: Mapped[str] = mapped_column(String(32), nullable=False, default="insufficient_evidence")
    uncertainty_notes: Mapped[Optional[str]] = mapped_column(Text)


class ResearchQuestionPaper(Base):
    __tablename__ = "research_question_papers"
    __table_args__ = (
        CheckConstraint(
            "literature_tier IN ('candidate','reading','core','foundation','excluded')",
            name="ck_research_question_papers_literature_tier",
        ),
    )

    research_question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_questions.id", ondelete="CASCADE"), primary_key=True
    )
    paper_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("papers.id", ondelete="RESTRICT"), primary_key=True, index=True
    )
    relation: Mapped[str] = mapped_column(String(32), nullable=False, default="relevant")
    literature_tier: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    relationship_note: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PaperResearchCard(Base, TimestampMixin):
    __tablename__ = "paper_research_cards"
    __table_args__ = (
        CheckConstraint(
            "status IN ('candidate','in_review','reviewed')",
            name="ck_paper_research_cards_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    paper_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    extraction_version: Mapped[str] = mapped_column(String(64), nullable=False, default="research_card_v1")
    fields: Mapped[dict[str, Any]] = mapped_column(json_type(), nullable=False, default=dict)
    important_quotes: Mapped[Optional[str]] = mapped_column(Text)
    my_interpretation: Mapped[Optional[str]] = mapped_column(Text)
    questions_raised: Mapped[Optional[str]] = mapped_column(Text)
    review_notes: Mapped[Optional[str]] = mapped_column(Text)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class ResearchDirection(Base, TimestampMixin):
    __tablename__ = "research_directions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('candidate','testing','selected','rejected')",
            name="ck_research_directions_status",
        ),
        CheckConstraint(
            "evidence_status IN ('supported','mixed','insufficient_evidence')",
            name="ck_research_directions_evidence_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    research_question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    rationale: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    evidence_status: Mapped[str] = mapped_column(String(32), nullable=False, default="insufficient_evidence")
    dimensions: Mapped[dict[str, Any]] = mapped_column(json_type(), nullable=False, default=dict)
    evidence_for: Mapped[Optional[str]] = mapped_column(Text)
    evidence_against: Mapped[Optional[str]] = mapped_column(Text)
    next_test: Mapped[Optional[str]] = mapped_column(Text)
    theory_note: Mapped[Optional[str]] = mapped_column(Text)
    data_note: Mapped[Optional[str]] = mapped_column(Text)
    method_note: Mapped[Optional[str]] = mapped_column(Text)


class ResearchDesign(Base, TimestampMixin):
    __tablename__ = "research_designs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','developing','ready')",
            name="ck_research_designs_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    research_question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_questions.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    selected_direction_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("research_directions.id", ondelete="SET NULL"), index=True
    )
    theoretical_framework: Mapped[Optional[str]] = mapped_column(Text)
    focal_constructs: Mapped[Optional[str]] = mapped_column(Text)
    independent_variables: Mapped[Optional[str]] = mapped_column(Text)
    dependent_variables: Mapped[Optional[str]] = mapped_column(Text)
    mediators: Mapped[Optional[str]] = mapped_column(Text)
    moderators: Mapped[Optional[str]] = mapped_column(Text)
    unit_of_analysis: Mapped[Optional[str]] = mapped_column(Text)
    context_population: Mapped[Optional[str]] = mapped_column(Text)
    data_sources: Mapped[Optional[str]] = mapped_column(Text)
    sampling_plan: Mapped[Optional[str]] = mapped_column(Text)
    methodology: Mapped[Optional[str]] = mapped_column(Text)
    analysis_plan: Mapped[Optional[str]] = mapped_column(Text)
    hypotheses: Mapped[Optional[str]] = mapped_column(Text)
    feasibility_notes: Mapped[Optional[str]] = mapped_column(Text)
    ethics_constraints: Mapped[Optional[str]] = mapped_column(Text)
    expected_contribution: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")


class ResearchQuestionSavedSearch(Base):
    __tablename__ = "research_question_saved_searches"

    research_question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_questions.id", ondelete="CASCADE"), primary_key=True
    )
    saved_search_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("saved_searches.id", ondelete="CASCADE"), primary_key=True
    )


class ResearchQuestionComparisonSet(Base):
    __tablename__ = "research_question_comparison_sets"

    research_question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_questions.id", ondelete="CASCADE"), primary_key=True
    )
    comparison_set_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("comparison_sets.id", ondelete="CASCADE"), primary_key=True
    )


class ResearchQuestionNote(Base, TimestampMixin):
    __tablename__ = "research_question_notes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    research_question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    note_markdown: Mapped[str] = mapped_column(Text, nullable=False)


class ComparisonSet(Base, TimestampMixin):
    __tablename__ = "comparison_sets"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)


class ComparisonSetPaper(Base):
    __tablename__ = "comparison_set_papers"

    comparison_set_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("comparison_sets.id", ondelete="CASCADE"), primary_key=True
    )
    paper_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("papers.id", ondelete="RESTRICT"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)


class ComparisonCell(Base, TimestampMixin):
    __tablename__ = "comparison_cells"
    __table_args__ = (
        UniqueConstraint("comparison_set_id", "paper_id", "field_name", name="uq_comparison_cell"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    comparison_set_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("comparison_sets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    paper_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("papers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    field_name: Mapped[str] = mapped_column(String(64), nullable=False)
    value_text: Mapped[Optional[str]] = mapped_column(Text)
    support_status: Mapped[str] = mapped_column(String(32), nullable=False, default="insufficient_evidence")
    origin: Mapped[str] = mapped_column(String(32), nullable=False, default="system_inference")


class GapAnalysis(Base, TimestampMixin):
    __tablename__ = "gap_analyses"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    research_question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    search_strategy: Mapped[str] = mapped_column(Text, nullable=False)
    inclusion_criteria: Mapped[str] = mapped_column(Text, nullable=False)
    exclusion_criteria: Mapped[str] = mapped_column(Text, nullable=False)
    research_clusters: Mapped[Optional[str]] = mapped_column(Text)
    agreements: Mapped[Optional[str]] = mapped_column(Text)
    conflicts: Mapped[Optional[str]] = mapped_column(Text)
    under_studied_contexts: Mapped[Optional[str]] = mapped_column(Text)
    gap_candidates: Mapped[Optional[str]] = mapped_column(Text)
    falsifiability_notes: Mapped[Optional[str]] = mapped_column(Text)
    follow_up_questions: Mapped[Optional[str]] = mapped_column(Text)
    theoretical_lenses: Mapped[Optional[str]] = mapped_column(Text)
    candidate_data_methods: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")


class EvidenceClaim(Base, TimestampMixin):
    __tablename__ = "evidence_claims"
    __table_args__ = (
        CheckConstraint(
            "claim_kind IN ('fact','paper_claim','system_inference','user_note')",
            name="ck_evidence_claim_kind",
        ),
        CheckConstraint(
            "support_status IN ('supported','mixed','contradicted','insufficient_evidence')",
            name="ck_evidence_support_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    claim_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    support_status: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_type: Mapped[Optional[str]] = mapped_column(String(64))
    scope_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    comparison_cell_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("comparison_cells.id", ondelete="CASCADE"), index=True
    )
    gap_analysis_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("gap_analyses.id", ondelete="CASCADE"), index=True
    )


class EvidenceLink(Base, TimestampMixin):
    __tablename__ = "evidence_links"
    __table_args__ = (
        UniqueConstraint("claim_id", "paper_id", "chunk_id", "relation", name="uq_evidence_link"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    claim_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence_claims.id", ondelete="CASCADE"), nullable=False, index=True
    )
    paper_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("papers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    chunk_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("paper_chunks.id", ondelete="RESTRICT"), index=True
    )
    relation: Mapped[str] = mapped_column(String(32), nullable=False)
    source_locator: Mapped[Optional[str]] = mapped_column(Text)


Index("ix_paper_chunks_paper_section", PaperChunk.paper_id, PaperChunk.section)
Index("ix_paper_topics_topic_paper", PaperTopic.topic_id, PaperTopic.paper_id)
