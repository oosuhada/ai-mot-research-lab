"""Add normalized research signal extracts.

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | Sequence[str] | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_signal_extracts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "research_card_id",
            sa.Uuid(),
            sa.ForeignKey("paper_research_cards.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("paper_id", sa.Uuid(), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("signal_type", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=250), nullable=False),
        sa.Column("normalized_label", sa.String(length=250), nullable=False),
        sa.Column("field_name", sa.String(length=64), nullable=False),
        sa.Column("evidence_text", sa.Text(), nullable=False),
        sa.Column("source_locator", sa.Text()),
        sa.Column("chunk_id", sa.Uuid(), sa.ForeignKey("paper_chunks.id", ondelete="SET NULL")),
        sa.Column("support_status", sa.String(length=32), nullable=False, server_default="supported"),
        sa.Column("extraction_version", sa.String(length=64), nullable=False, server_default="signal_extract_v1"),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "signal_type IN ('limitation','dataset','method','evaluation_metric','future_research')",
            name="ck_research_signal_extracts_type",
        ),
        sa.UniqueConstraint(
            "research_card_id",
            "signal_type",
            "normalized_label",
            "field_name",
            name="uq_research_signal_extract_card_signal",
        ),
    )
    op.create_index("ix_research_signal_extracts_research_card_id", "research_signal_extracts", ["research_card_id"])
    op.create_index("ix_research_signal_extracts_paper", "research_signal_extracts", ["paper_id"])
    op.create_index("ix_research_signal_extracts_chunk", "research_signal_extracts", ["chunk_id"])
    op.create_index(
        "ix_research_signal_extracts_type_label",
        "research_signal_extracts",
        ["signal_type", "normalized_label"],
    )


def downgrade() -> None:
    op.drop_index("ix_research_signal_extracts_type_label", table_name="research_signal_extracts")
    op.drop_index("ix_research_signal_extracts_chunk", table_name="research_signal_extracts")
    op.drop_index("ix_research_signal_extracts_paper", table_name="research_signal_extracts")
    op.drop_index("ix_research_signal_extracts_research_card_id", table_name="research_signal_extracts")
    op.drop_table("research_signal_extracts")
