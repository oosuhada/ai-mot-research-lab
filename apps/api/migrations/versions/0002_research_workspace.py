"""Add research-question workspace links and comparison origins.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.add_column("research_questions", sa.Column("importance_notes", sa.Text()))
    op.add_column(
        "research_questions",
        sa.Column("evidence_status", sa.String(32), nullable=False, server_default="insufficient_evidence"),
    )
    op.add_column("research_questions", sa.Column("uncertainty_notes", sa.Text()))
    op.create_check_constraint(
        "ck_research_questions_evidence_status",
        "research_questions",
        "evidence_status IN ('supported','mixed','insufficient_evidence')",
    )

    op.create_table(
        "research_question_papers",
        sa.Column(
            "research_question_id",
            sa.Uuid(),
            sa.ForeignKey("research_questions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("paper_id", sa.Uuid(), sa.ForeignKey("papers.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("relation", sa.String(32), nullable=False, server_default="relevant"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_research_question_papers_paper", "research_question_papers", ["paper_id"])

    op.create_table(
        "research_question_saved_searches",
        sa.Column(
            "research_question_id",
            sa.Uuid(),
            sa.ForeignKey("research_questions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "saved_search_id",
            sa.Uuid(),
            sa.ForeignKey("saved_searches.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.create_table(
        "research_question_comparison_sets",
        sa.Column(
            "research_question_id",
            sa.Uuid(),
            sa.ForeignKey("research_questions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "comparison_set_id",
            sa.Uuid(),
            sa.ForeignKey("comparison_sets.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.create_table(
        "research_question_notes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "research_question_id",
            sa.Uuid(),
            sa.ForeignKey("research_questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("note_markdown", sa.Text(), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_research_question_notes_question", "research_question_notes", ["research_question_id"])

    op.add_column(
        "comparison_cells",
        sa.Column("origin", sa.String(32), nullable=False, server_default="system_inference"),
    )
    op.execute(
        "UPDATE comparison_cells SET origin = CASE "
        "WHEN support_status = 'supported' THEN 'paper_evidence' ELSE 'system_inference' END"
    )
    op.create_check_constraint(
        "ck_comparison_cells_origin",
        "comparison_cells",
        "origin IN ('paper_evidence','system_inference','user_note')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_comparison_cells_origin", "comparison_cells", type_="check")
    op.drop_column("comparison_cells", "origin")
    op.drop_index("ix_research_question_notes_question", table_name="research_question_notes")
    op.drop_table("research_question_notes")
    op.drop_table("research_question_comparison_sets")
    op.drop_table("research_question_saved_searches")
    op.drop_index("ix_research_question_papers_paper", table_name="research_question_papers")
    op.drop_table("research_question_papers")
    op.drop_constraint("ck_research_questions_evidence_status", "research_questions", type_="check")
    op.drop_column("research_questions", "uncertainty_notes")
    op.drop_column("research_questions", "evidence_status")
    op.drop_column("research_questions", "importance_notes")
