"""Create the provenance-aware research schema.

Revision ID: 0001
Revises: None
Create Date: 2026-08-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "venues",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("openalex_id", sa.String(64), unique=True),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("issn_l", sa.String(32)),
        sa.Column("publisher", sa.String(500)),
        sa.Column("venue_type", sa.String(64)),
        *timestamps(),
    )
    op.create_index("ix_venues_issn_l", "venues", ["issn_l"])

    op.create_table(
        "authors",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("openalex_id", sa.String(64), unique=True),
        sa.Column("s2_id", sa.String(64), unique=True),
        sa.Column("orcid", sa.String(32), unique=True),
        sa.Column("display_name", sa.String(500), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_authors_display_name", "authors", ["display_name"])

    op.create_table(
        "institutions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("openalex_id", sa.String(64), unique=True),
        sa.Column("ror", sa.String(64), unique=True),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("country_code", sa.String(2)),
        sa.Column("institution_type", sa.String(64)),
        *timestamps(),
    )
    op.create_index("ix_institutions_name", "institutions", ["name"])

    op.create_table(
        "topics",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("slug", sa.String(128), nullable=False, unique=True),
        sa.Column("display_name", sa.String(250), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("source_record_id", sa.String(128)),
        sa.Column("description", sa.Text()),
        *timestamps(),
    )

    op.create_table(
        "papers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("doi", sa.String(255), unique=True),
        sa.Column("openalex_id", sa.String(64), unique=True),
        sa.Column("s2_id", sa.String(64), unique=True),
        sa.Column("arxiv_id", sa.String(64), unique=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("abstract", sa.Text()),
        sa.Column("publication_date", sa.Date()),
        sa.Column("publication_year", sa.Integer()),
        sa.Column("language", sa.String(16)),
        sa.Column("work_type", sa.String(64)),
        sa.Column("venue_id", sa.Uuid(), sa.ForeignKey("venues.id", ondelete="SET NULL")),
        sa.Column("publisher", sa.String(500)),
        sa.Column("oa_status", sa.String(32)),
        sa.Column("is_oa", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("primary_url", sa.Text()),
        sa.Column("pdf_url", sa.Text()),
        sa.Column("retraction_status", sa.String(32), nullable=False, server_default="none"),
        sa.Column("correction_status", sa.String(32), nullable=False, server_default="none"),
        sa.Column("license", sa.String(255)),
        sa.Column("primary_source", sa.String(64), nullable=False),
        sa.Column("source_record_id", sa.String(255), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "provenance",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("is_seminal_exception", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(
                "setweight(to_tsvector('simple', coalesce(title, '')), 'A') || "
                "setweight(to_tsvector('simple', coalesce(abstract, '')), 'B')",
                persisted=True,
            ),
        ),
        *timestamps(),
        sa.CheckConstraint("publication_year IS NULL OR publication_year >= 1400", name="ck_papers_year"),
    )
    for column in [
        "doi",
        "openalex_id",
        "s2_id",
        "arxiv_id",
        "publication_year",
        "work_type",
        "venue_id",
        "oa_status",
    ]:
        op.create_index(f"ix_papers_{column}", "papers", [column])
    op.create_index("ix_papers_search_vector", "papers", ["search_vector"], postgresql_using="gin")

    op.create_table(
        "paper_authors",
        sa.Column("paper_id", sa.Uuid(), sa.ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("author_id", sa.Uuid(), sa.ForeignKey("authors.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("author_position", sa.Integer(), nullable=False),
        sa.Column("is_corresponding", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("raw_affiliation", sa.Text()),
        sa.UniqueConstraint("paper_id", "author_id", name="uq_paper_authors_pair"),
    )

    op.create_table(
        "author_institutions",
        sa.Column("author_id", sa.Uuid(), sa.ForeignKey("authors.id", ondelete="CASCADE"), primary_key=True),
        sa.Column(
            "institution_id",
            sa.Uuid(),
            sa.ForeignKey("institutions.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("source", sa.String(64), primary_key=True),
    )

    op.create_table(
        "paper_topics",
        sa.Column("paper_id", sa.Uuid(), sa.ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("topic_id", sa.Uuid(), sa.ForeignKey("topics.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("score", sa.Float()),
        sa.Column("assignment_source", sa.String(64), nullable=False),
    )
    op.create_index("ix_paper_topics_topic_paper", "paper_topics", ["topic_id", "paper_id"])

    op.create_table(
        "citations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "citing_paper_id",
            sa.Uuid(),
            sa.ForeignKey("papers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("cited_paper_id", sa.Uuid(), sa.ForeignKey("papers.id", ondelete="RESTRICT")),
        sa.Column("cited_external_id", sa.String(255)),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("is_influential", sa.Boolean()),
        sa.Column("context_locator", sa.Text()),
        *timestamps(),
        sa.UniqueConstraint(
            "citing_paper_id", "cited_paper_id", "cited_external_id", name="uq_citations_edge"
        ),
    )
    op.create_index("ix_citations_citing_paper_id", "citations", ["citing_paper_id"])
    op.create_index("ix_citations_cited_paper_id", "citations", ["cited_paper_id"])
    op.create_index("ix_citations_cited_external_id", "citations", ["cited_external_id"])

    op.create_table(
        "citation_snapshots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("paper_id", sa.Uuid(), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("citation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("oa_status", sa.String(32)),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("paper_id", "source", "captured_at", name="uq_citation_snapshot_time"),
    )
    op.create_index("ix_citation_snapshots_paper_id", "citation_snapshots", ["paper_id"])

    op.create_table(
        "paper_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("paper_id", sa.Uuid(), sa.ForeignKey("papers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("source_record_id", sa.String(255), nullable=False),
        sa.Column("version_label", sa.String(64)),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("license", sa.String(255)),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column(
            "source_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.UniqueConstraint(
            "paper_id", "source", "source_record_id", "payload_hash", name="uq_paper_version"
        ),
    )
    op.create_index("ix_paper_versions_paper_id", "paper_versions", ["paper_id"])

    op.create_table(
        "paper_embeddings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("paper_id", sa.Uuid(), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False, server_default="384"),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("paper_id", "provider", "model", name="uq_paper_embedding"),
    )
    op.create_index("ix_paper_embeddings_paper_id", "paper_embeddings", ["paper_id"])
    op.create_index(
        "ix_paper_embeddings_hnsw_cosine",
        "paper_embeddings",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    op.create_table(
        "paper_chunks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("paper_id", sa.Uuid(), sa.ForeignKey("papers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("paper_version_id", sa.Uuid(), sa.ForeignKey("paper_versions.id", ondelete="RESTRICT")),
        sa.Column("section", sa.String(500)),
        sa.Column("page_start", sa.Integer()),
        sa.Column("page_end", sa.Integer()),
        sa.Column("char_start", sa.Integer()),
        sa.Column("char_end", sa.Integer()),
        sa.Column("source_locator", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("text_hash", sa.String(64), nullable=False),
        sa.Column("language", sa.String(16)),
        sa.Column("embedding", Vector(384)),
        *timestamps(),
        sa.UniqueConstraint("paper_id", "text_hash", name="uq_paper_chunk_hash"),
    )
    op.create_index("ix_paper_chunks_paper_id", "paper_chunks", ["paper_id"])
    op.create_index("ix_paper_chunks_paper_version_id", "paper_chunks", ["paper_version_id"])
    op.create_index("ix_paper_chunks_paper_section", "paper_chunks", ["paper_id", "section"])
    op.create_index(
        "ix_paper_chunks_hnsw_cosine",
        "paper_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
        postgresql_where=sa.text("embedding IS NOT NULL"),
    )

    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="running"),
        sa.Column("taxonomy_version", sa.String(32), nullable=False),
        sa.Column(
            "query_spec",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "checkpoint",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("fetched_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("accepted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("inserted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("error_message", sa.Text()),
    )
    op.create_index("ix_ingestion_runs_source", "ingestion_runs", ["source"])

    op.create_table(
        "saved_searches",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(250), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column(
            "filters",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        *timestamps(),
    )

    op.create_table(
        "reading_queue",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("paper_id", sa.Uuid(), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="unread"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        *timestamps(),
        sa.CheckConstraint(
            "status IN ('unread','skimming','reading','read','archived')",
            name="ck_reading_queue_status",
        ),
    )
    op.create_index("ix_reading_queue_paper_id", "reading_queue", ["paper_id"])

    op.create_table(
        "paper_notes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("paper_id", sa.Uuid(), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("note_markdown", sa.Text(), nullable=False),
        sa.Column("source_locator", sa.Text()),
        *timestamps(),
    )
    op.create_index("ix_paper_notes_paper_id", "paper_notes", ["paper_id"])

    op.create_table(
        "tags",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False, unique=True),
        *timestamps(),
    )
    op.create_table(
        "paper_tags",
        sa.Column("paper_id", sa.Uuid(), sa.ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tag_id", sa.Uuid(), sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "research_questions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("motivation", sa.Text()),
        sa.Column("scope_notes", sa.Text()),
        sa.Column("status", sa.String(32), nullable=False, server_default="exploring"),
        *timestamps(),
    )

    op.create_table(
        "comparison_sets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("description", sa.Text()),
        *timestamps(),
    )
    op.create_table(
        "comparison_set_papers",
        sa.Column(
            "comparison_set_id",
            sa.Uuid(),
            sa.ForeignKey("comparison_sets.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("paper_id", sa.Uuid(), sa.ForeignKey("papers.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("position", sa.Integer(), nullable=False),
    )

    op.create_table(
        "comparison_cells",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "comparison_set_id",
            sa.Uuid(),
            sa.ForeignKey("comparison_sets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("paper_id", sa.Uuid(), sa.ForeignKey("papers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("field_name", sa.String(64), nullable=False),
        sa.Column("value_text", sa.Text()),
        sa.Column(
            "support_status", sa.String(32), nullable=False, server_default="insufficient_evidence"
        ),
        *timestamps(),
        sa.UniqueConstraint("comparison_set_id", "paper_id", "field_name", name="uq_comparison_cell"),
    )
    op.create_index("ix_comparison_cells_comparison_set_id", "comparison_cells", ["comparison_set_id"])
    op.create_index("ix_comparison_cells_paper_id", "comparison_cells", ["paper_id"])

    op.create_table(
        "gap_analyses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "research_question_id",
            sa.Uuid(),
            sa.ForeignKey("research_questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("search_strategy", sa.Text(), nullable=False),
        sa.Column("inclusion_criteria", sa.Text(), nullable=False),
        sa.Column("exclusion_criteria", sa.Text(), nullable=False),
        sa.Column("research_clusters", sa.Text()),
        sa.Column("agreements", sa.Text()),
        sa.Column("conflicts", sa.Text()),
        sa.Column("under_studied_contexts", sa.Text()),
        sa.Column("gap_candidates", sa.Text()),
        sa.Column("falsifiability_notes", sa.Text()),
        sa.Column("follow_up_questions", sa.Text()),
        sa.Column("theoretical_lenses", sa.Text()),
        sa.Column("candidate_data_methods", sa.Text()),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        *timestamps(),
    )
    op.create_index("ix_gap_analyses_research_question_id", "gap_analyses", ["research_question_id"])

    op.create_table(
        "evidence_claims",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("claim_kind", sa.String(32), nullable=False),
        sa.Column("support_status", sa.String(32), nullable=False),
        sa.Column("scope_type", sa.String(64)),
        sa.Column("scope_id", sa.Uuid()),
        sa.Column(
            "comparison_cell_id",
            sa.Uuid(),
            sa.ForeignKey("comparison_cells.id", ondelete="CASCADE"),
        ),
        sa.Column("gap_analysis_id", sa.Uuid(), sa.ForeignKey("gap_analyses.id", ondelete="CASCADE")),
        *timestamps(),
        sa.CheckConstraint(
            "claim_kind IN ('fact','paper_claim','system_inference','user_note')",
            name="ck_evidence_claim_kind",
        ),
        sa.CheckConstraint(
            "support_status IN ('supported','mixed','contradicted','insufficient_evidence')",
            name="ck_evidence_support_status",
        ),
    )
    op.create_index("ix_evidence_claims_comparison_cell_id", "evidence_claims", ["comparison_cell_id"])
    op.create_index("ix_evidence_claims_gap_analysis_id", "evidence_claims", ["gap_analysis_id"])

    op.create_table(
        "evidence_links",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "claim_id", sa.Uuid(), sa.ForeignKey("evidence_claims.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("paper_id", sa.Uuid(), sa.ForeignKey("papers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("chunk_id", sa.Uuid(), sa.ForeignKey("paper_chunks.id", ondelete="RESTRICT")),
        sa.Column("relation", sa.String(32), nullable=False),
        sa.Column("source_locator", sa.Text()),
        *timestamps(),
        sa.UniqueConstraint("claim_id", "paper_id", "chunk_id", "relation", name="uq_evidence_link"),
    )
    op.create_index("ix_evidence_links_claim_id", "evidence_links", ["claim_id"])
    op.create_index("ix_evidence_links_paper_id", "evidence_links", ["paper_id"])
    op.create_index("ix_evidence_links_chunk_id", "evidence_links", ["chunk_id"])


def downgrade() -> None:
    for table in [
        "evidence_links",
        "evidence_claims",
        "gap_analyses",
        "comparison_cells",
        "comparison_set_papers",
        "comparison_sets",
        "research_questions",
        "paper_tags",
        "tags",
        "paper_notes",
        "reading_queue",
        "saved_searches",
        "ingestion_runs",
        "paper_chunks",
        "paper_embeddings",
        "paper_versions",
        "citation_snapshots",
        "citations",
        "paper_topics",
        "author_institutions",
        "paper_authors",
        "papers",
        "topics",
        "institutions",
        "authors",
        "venues",
    ]:
        op.drop_table(table)

