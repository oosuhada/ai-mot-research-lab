"""Add OpenCitations Meta identifier to canonical papers.

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("papers", sa.Column("opencitations_omid", sa.String(length=64)))
    op.create_index(
        "ix_papers_opencitations_omid",
        "papers",
        ["opencitations_omid"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_papers_opencitations_omid", table_name="papers")
    op.drop_column("papers", "opencitations_omid")
