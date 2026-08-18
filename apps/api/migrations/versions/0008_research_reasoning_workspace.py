"""Add structured reading, topic selection, and research-design workflow.

Revision ID: 0008
Revises: 0006, 0007
Create Date: 2026-08-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | Sequence[str] | None = ("0006", "0007")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def json_column_type() -> sa.TypeEngine[object]:
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.add_column(
        "research_question_papers",
        sa.Column("literature_tier", sa.String(32), nullable=False, server_default="candidate"),
    )
    op.add_column("research_question_papers", sa.Column("relationship_note", sa.Text()))
    op.create_check_constraint(
        "ck_research_question_papers_literature_tier",
        "research_question_papers",
        "literature_tier IN ('candidate','reading','core','foundation','excluded')",
    )

    op.create_table(
        "paper_research_cards",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("paper_id", sa.Uuid(), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="candidate"),
        sa.Column("extraction_version", sa.String(64), nullable=False, server_default="research_card_v1"),
        sa.Column("fields", json_column_type(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("important_quotes", sa.Text()),
        sa.Column("my_interpretation", sa.Text()),
        sa.Column("questions_raised", sa.Text()),
        sa.Column("review_notes", sa.Text()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        *timestamps(),
        sa.CheckConstraint(
            "status IN ('candidate','in_review','reviewed')",
            name="ck_paper_research_cards_status",
        ),
    )
    op.create_index("ix_paper_research_cards_paper_id", "paper_research_cards", ["paper_id"], unique=True)

    op.create_table(
        "research_directions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "research_question_id",
            sa.Uuid(),
            sa.ForeignKey("research_questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("rationale", sa.Text()),
        sa.Column("status", sa.String(32), nullable=False, server_default="candidate"),
        sa.Column("evidence_status", sa.String(32), nullable=False, server_default="insufficient_evidence"),
        sa.Column("dimensions", json_column_type(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("evidence_for", sa.Text()),
        sa.Column("evidence_against", sa.Text()),
        sa.Column("next_test", sa.Text()),
        sa.Column("theory_note", sa.Text()),
        sa.Column("data_note", sa.Text()),
        sa.Column("method_note", sa.Text()),
        *timestamps(),
        sa.CheckConstraint(
            "status IN ('candidate','testing','selected','rejected')",
            name="ck_research_directions_status",
        ),
        sa.CheckConstraint(
            "evidence_status IN ('supported','mixed','insufficient_evidence')",
            name="ck_research_directions_evidence_status",
        ),
    )
    op.create_index("ix_research_directions_question", "research_directions", ["research_question_id"])

    op.create_table(
        "research_designs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "research_question_id",
            sa.Uuid(),
            sa.ForeignKey("research_questions.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "selected_direction_id",
            sa.Uuid(),
            sa.ForeignKey("research_directions.id", ondelete="SET NULL"),
        ),
        sa.Column("theoretical_framework", sa.Text()),
        sa.Column("focal_constructs", sa.Text()),
        sa.Column("independent_variables", sa.Text()),
        sa.Column("dependent_variables", sa.Text()),
        sa.Column("mediators", sa.Text()),
        sa.Column("moderators", sa.Text()),
        sa.Column("unit_of_analysis", sa.Text()),
        sa.Column("context_population", sa.Text()),
        sa.Column("data_sources", sa.Text()),
        sa.Column("sampling_plan", sa.Text()),
        sa.Column("methodology", sa.Text()),
        sa.Column("analysis_plan", sa.Text()),
        sa.Column("hypotheses", sa.Text()),
        sa.Column("feasibility_notes", sa.Text()),
        sa.Column("ethics_constraints", sa.Text()),
        sa.Column("expected_contribution", sa.Text()),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        *timestamps(),
        sa.CheckConstraint(
            "status IN ('draft','developing','ready')",
            name="ck_research_designs_status",
        ),
    )
    op.create_index("ix_research_designs_question", "research_designs", ["research_question_id"], unique=True)
    op.create_index("ix_research_designs_direction", "research_designs", ["selected_direction_id"])


def downgrade() -> None:
    op.drop_index("ix_research_designs_direction", table_name="research_designs")
    op.drop_index("ix_research_designs_question", table_name="research_designs")
    op.drop_table("research_designs")
    op.drop_index("ix_research_directions_question", table_name="research_directions")
    op.drop_table("research_directions")
    op.drop_index("ix_paper_research_cards_paper_id", table_name="paper_research_cards")
    op.drop_table("paper_research_cards")
    op.drop_constraint(
        "ck_research_question_papers_literature_tier",
        "research_question_papers",
        type_="check",
    )
    op.drop_column("research_question_papers", "relationship_note")
    op.drop_column("research_question_papers", "literature_tier")
