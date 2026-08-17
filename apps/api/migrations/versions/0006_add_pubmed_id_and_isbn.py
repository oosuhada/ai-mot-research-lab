"""Add pubmed_id and isbn columns to papers table.

Revision ID: 0007
Revises: 0005
Create Date: 2026-08-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add pubmed_id column (PMID)
    op.add_column("papers", sa.Column("pubmed_id", sa.String(length=32), nullable=True))
    op.create_index("ix_papers_pubmed_id", "papers", ["pubmed_id"])

    # Add isbn column
    op.add_column("papers", sa.Column("isbn", sa.String(length=32), nullable=True))
    op.create_index("ix_papers_isbn", "papers", ["isbn"])


def downgrade() -> None:
    op.drop_index("ix_papers_isbn", table_name="papers")
    op.drop_column("papers", "isbn")
    op.drop_index("ix_papers_pubmed_id", table_name="papers")
    op.drop_column("papers", "pubmed_id")
