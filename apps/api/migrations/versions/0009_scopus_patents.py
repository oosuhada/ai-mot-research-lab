"""Add Scopus identifiers and patent evidence storage.

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def json_column_type() -> sa.TypeEngine[object]:
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.add_column("papers", sa.Column("scopus_eid", sa.String(length=64)))
    op.add_column("papers", sa.Column("scopus_id", sa.String(length=64)))
    op.create_index("ix_papers_scopus_eid", "papers", ["scopus_eid"], unique=True)
    op.create_index("ix_papers_scopus_id", "papers", ["scopus_id"], unique=True)

    op.create_table(
        "patent_documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("application_number", sa.String(length=128)),
        sa.Column("publication_number", sa.String(length=128)),
        sa.Column("registration_number", sa.String(length=128)),
        sa.Column("jurisdiction", sa.String(length=16)),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("abstract", sa.Text()),
        sa.Column("filing_date", sa.Date()),
        sa.Column("publication_date", sa.Date()),
        sa.Column("priority_date", sa.Date()),
        sa.Column("applicants", json_column_type(), nullable=False),
        sa.Column("inventors", json_column_type(), nullable=False),
        sa.Column("ipc_codes", json_column_type(), nullable=False),
        sa.Column("cpc_codes", json_column_type(), nullable=False),
        sa.Column("family_id", sa.String(length=255)),
        sa.Column("legal_status", sa.String(length=128)),
        sa.Column("primary_source", sa.String(length=64), nullable=False),
        sa.Column("source_record_id", sa.String(length=255), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provenance", json_column_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("primary_source", "source_record_id", name="uq_patent_source_record"),
    )
    op.create_index("ix_patent_documents_application_number", "patent_documents", ["application_number"])
    op.create_index("ix_patent_documents_publication_number", "patent_documents", ["publication_number"])
    op.create_index("ix_patent_documents_registration_number", "patent_documents", ["registration_number"])
    op.create_index("ix_patent_documents_jurisdiction", "patent_documents", ["jurisdiction"])
    op.create_index("ix_patent_documents_filing_date", "patent_documents", ["filing_date"])
    op.create_index("ix_patent_documents_publication_date", "patent_documents", ["publication_date"])
    op.create_index("ix_patent_documents_priority_date", "patent_documents", ["priority_date"])
    op.create_index("ix_patent_documents_family_id", "patent_documents", ["family_id"])
    op.create_index("ix_patent_documents_legal_status", "patent_documents", ["legal_status"])
    op.create_index(
        "ix_patent_jurisdiction_application",
        "patent_documents",
        ["jurisdiction", "application_number"],
    )
    op.create_index(
        "ix_patent_jurisdiction_publication",
        "patent_documents",
        ["jurisdiction", "publication_number"],
    )


def downgrade() -> None:
    op.drop_table("patent_documents")
    op.drop_index("ix_papers_scopus_id", table_name="papers")
    op.drop_index("ix_papers_scopus_eid", table_name="papers")
    op.drop_column("papers", "scopus_id")
    op.drop_column("papers", "scopus_eid")
