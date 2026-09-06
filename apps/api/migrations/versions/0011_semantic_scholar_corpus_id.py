"""Add Semantic Scholar corpus ID to canonical papers.

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | Sequence[str] | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("papers", sa.Column("s2_corpus_id", sa.String(length=32)))
    op.create_index("ix_papers_s2_corpus_id", "papers", ["s2_corpus_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_papers_s2_corpus_id", table_name="papers")
    op.drop_column("papers", "s2_corpus_id")
