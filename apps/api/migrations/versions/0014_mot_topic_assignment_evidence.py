"""Add versioned MOT topic assignment evidence.

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014"
down_revision: str | Sequence[str] | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "paper_topic_assignment_evidence",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("paper_id", sa.Uuid(), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("topic_id", sa.Uuid(), sa.ForeignKey("topics.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assignment_key", sa.String(length=64), nullable=False),
        sa.Column("taxonomy_version", sa.String(length=64), nullable=False),
        sa.Column("assignment_source", sa.String(length=64), nullable=False),
        sa.Column("rule_id", sa.String(length=160)),
        sa.Column("evidence_kind", sa.String(length=32), nullable=False, server_default="unknown"),
        sa.Column("evidence_text", sa.Text()),
        sa.Column("source_locator", sa.Text()),
        sa.Column(
            "matched_terms",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column(
            "review_status",
            sa.String(length=32),
            nullable=False,
            server_default="automatic_candidate",
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("reviewer_note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "review_status IN ('automatic_candidate','human_confirmed','human_rejected','needs_review','legacy_unreviewed')",
            name="ck_paper_topic_assignment_evidence_review_status",
        ),
        sa.CheckConstraint(
            "evidence_kind IN ('title','abstract','full_text','metadata','legacy','unknown')",
            name="ck_paper_topic_assignment_evidence_kind",
        ),
        sa.UniqueConstraint("assignment_key", name="uq_paper_topic_assignment_evidence_key"),
    )
    op.create_index(
        "ix_paper_topic_assignment_evidence_paper_topic",
        "paper_topic_assignment_evidence",
        ["paper_id", "topic_id"],
    )
    op.create_index(
        "ix_paper_topic_assignment_evidence_review",
        "paper_topic_assignment_evidence",
        ["review_status", "taxonomy_version"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_paper_topic_assignment_evidence_review",
        table_name="paper_topic_assignment_evidence",
    )
    op.drop_index(
        "ix_paper_topic_assignment_evidence_paper_topic",
        table_name="paper_topic_assignment_evidence",
    )
    op.drop_table("paper_topic_assignment_evidence")
