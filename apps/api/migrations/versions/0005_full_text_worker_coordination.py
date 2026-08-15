"""Add full-text worker leases and source-attempt observability.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("full_text_queue", sa.Column("failure_kind", sa.String(length=64), nullable=True))
    op.add_column("full_text_queue", sa.Column("worker_id", sa.String(length=255), nullable=True))
    op.add_column("full_text_queue", sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("full_text_queue", sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_full_text_queue_failure_kind", "full_text_queue", ["failure_kind"])
    op.create_index("ix_full_text_queue_worker_id", "full_text_queue", ["worker_id"])
    op.create_index("ix_full_text_queue_lease_expires_at", "full_text_queue", ["lease_expires_at"])
    op.create_index(
        "ix_full_text_queue_claimable",
        "full_text_queue",
        ["status", "rights_status", "next_attempt_at", "lease_expires_at", "priority"],
    )

    op.create_table(
        "full_text_source_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("queue_item_id", sa.Uuid(), nullable=False),
        sa.Column("paper_id", sa.Uuid(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=True),
        sa.Column("publisher", sa.String(length=500), nullable=True),
        sa.Column("source_kind", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("failure_kind", sa.String(length=64), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["paper_id"], ["papers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["queue_item_id"], ["full_text_queue.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_full_text_source_attempts_queue_item_id", "full_text_source_attempts", ["queue_item_id"])
    op.create_index("ix_full_text_source_attempts_paper_id", "full_text_source_attempts", ["paper_id"])
    op.create_index("ix_full_text_source_attempts_domain", "full_text_source_attempts", ["domain"])
    op.create_index("ix_full_text_source_attempts_publisher", "full_text_source_attempts", ["publisher"])
    op.create_index("ix_full_text_source_attempts_failure_kind", "full_text_source_attempts", ["failure_kind"])


def downgrade() -> None:
    op.drop_index("ix_full_text_source_attempts_failure_kind", table_name="full_text_source_attempts")
    op.drop_index("ix_full_text_source_attempts_publisher", table_name="full_text_source_attempts")
    op.drop_index("ix_full_text_source_attempts_domain", table_name="full_text_source_attempts")
    op.drop_index("ix_full_text_source_attempts_paper_id", table_name="full_text_source_attempts")
    op.drop_index("ix_full_text_source_attempts_queue_item_id", table_name="full_text_source_attempts")
    op.drop_table("full_text_source_attempts")
    op.drop_index("ix_full_text_queue_claimable", table_name="full_text_queue")
    op.drop_index("ix_full_text_queue_lease_expires_at", table_name="full_text_queue")
    op.drop_index("ix_full_text_queue_worker_id", table_name="full_text_queue")
    op.drop_index("ix_full_text_queue_failure_kind", table_name="full_text_queue")
    op.drop_column("full_text_queue", "lease_expires_at")
    op.drop_column("full_text_queue", "claimed_at")
    op.drop_column("full_text_queue", "worker_id")
    op.drop_column("full_text_queue", "failure_kind")
