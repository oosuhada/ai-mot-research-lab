"""Add corpus intelligence, evidence-depth, and localization foundations.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-24
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


ADOPTION_SUBAXES = (
    ("adoption-determinants", "Adoption determinants"),
    ("organizational-readiness", "Organizational readiness and complementary assets"),
    ("ai-capability-development", "AI capability development"),
    ("workflow-transformation", "Workflow and process transformation"),
    ("productivity-performance", "Productivity and operational performance"),
    ("innovation-outcomes", "Innovation outcomes"),
    ("value-roi", "Financial value and ROI measurement"),
    ("scaling-implementation", "Scaling and implementation"),
    ("workforce-human-ai", "Workforce, skills, and human–AI collaboration"),
)


def timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.add_column("topics", sa.Column("parent_topic_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_topics_parent_topic_id",
        "topics",
        "topics",
        ["parent_topic_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_topics_parent_topic_id", "topics", ["parent_topic_id"])

    op.create_table(
        "paper_content_profiles",
        sa.Column("paper_id", sa.Uuid(), sa.ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("abstract_status", sa.String(32), nullable=False, server_default="missing"),
        sa.Column("full_text_status", sa.String(32), nullable=False, server_default="not_requested"),
        sa.Column("full_text_access", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("rights_status", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("full_text_priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("abstract_updated_at", sa.DateTime(timezone=True)),
        sa.Column("full_text_updated_at", sa.DateTime(timezone=True)),
        *timestamps(),
        sa.CheckConstraint(
            "abstract_status IN ('missing','available','translated')",
            name="ck_paper_content_profiles_abstract_status",
        ),
        sa.CheckConstraint(
            "full_text_status IN ('not_requested','queued','processing','available','restricted','failed')",
            name="ck_paper_content_profiles_full_text_status",
        ),
    )

    op.create_table(
        "full_text_queue",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "paper_id",
            sa.Uuid(),
            sa.ForeignKey("papers.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "reason_factors",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("rights_status", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
        *timestamps(),
        sa.CheckConstraint(
            "status IN ('pending','processing','completed','restricted','failed')",
            name="ck_full_text_queue_status",
        ),
    )
    op.create_index("ix_full_text_queue_priority", "full_text_queue", ["status", "priority"])

    op.create_table(
        "paper_localizations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("paper_id", sa.Uuid(), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("locale", sa.String(16), nullable=False),
        sa.Column("title", sa.Text()),
        sa.Column("abstract", sa.Text()),
        sa.Column(
            "keywords",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(64)),
        sa.Column("model", sa.String(128)),
        sa.Column("translated_at", sa.DateTime(timezone=True)),
        *timestamps(),
        sa.UniqueConstraint("paper_id", "locale", name="uq_paper_localizations_locale"),
    )
    op.create_index("ix_paper_localizations_paper", "paper_localizations", ["paper_id"])

    op.create_table(
        "daily_discovery_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("paper_id", sa.Uuid(), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_kind", sa.String(32), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("relevance_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("novelty_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("summary", sa.Text()),
        sa.Column(
            "signals",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        *timestamps(),
        sa.UniqueConstraint("paper_id", "event_kind", "event_date", name="uq_daily_discovery_event"),
    )
    op.create_index("ix_daily_discovery_events_date", "daily_discovery_events", ["event_date"])

    op.create_table(
        "research_opportunities",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("slug", sa.String(160), nullable=False, unique=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("hypothesis", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("axis_slug", sa.String(128)),
        sa.Column("evidence_status", sa.String(32), nullable=False, server_default="insufficient_evidence"),
        sa.Column("coverage_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("adjacent_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "signals",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("recommended_method", sa.String(250)),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        *timestamps(),
    )

    op.execute(
        """
        INSERT INTO paper_content_profiles (
            paper_id, abstract_status, full_text_status, full_text_access, rights_status,
            full_text_priority, abstract_updated_at, full_text_updated_at
        )
        SELECT
            p.id,
            CASE WHEN p.abstract IS NOT NULL AND length(trim(p.abstract)) > 0 THEN 'available' ELSE 'missing' END,
            CASE
                WHEN EXISTS (SELECT 1 FROM paper_chunks pc WHERE pc.paper_id = p.id) THEN 'available'
                WHEN p.is_oa = true AND p.pdf_url IS NOT NULL THEN 'queued'
                WHEN p.is_oa = false THEN 'restricted'
                ELSE 'not_requested'
            END,
            CASE WHEN p.is_oa = true THEN 'open_access' WHEN p.is_oa = false THEN 'paywalled' ELSE 'unknown' END,
            CASE WHEN p.is_oa = true THEN 'open_access' ELSE 'unknown' END,
            CASE WHEN p.is_oa = true AND p.pdf_url IS NOT NULL THEN 50 ELSE 0 END,
            CASE WHEN p.abstract IS NOT NULL AND length(trim(p.abstract)) > 0 THEN p.updated_at ELSE NULL END,
            CASE WHEN EXISTS (SELECT 1 FROM paper_chunks pc WHERE pc.paper_id = p.id) THEN p.updated_at ELSE NULL END
        FROM papers p
        ON CONFLICT (paper_id) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO full_text_queue (id, paper_id, status, priority, reason_factors, rights_status)
        SELECT
            gen_random_uuid(), p.id, 'pending', 50,
            '{"open_access": true, "pdf_available": true}'::jsonb,
            'open_access'
        FROM papers p
        WHERE p.is_oa = true
          AND p.pdf_url IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM paper_chunks pc WHERE pc.paper_id = p.id)
        ON CONFLICT (paper_id) DO NOTHING
        """
    )

    parent_slug = "ai-adoption-business-value"
    for slug, display_name in ADOPTION_SUBAXES:
        topic_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-mot-taxonomy:{slug}"))
        op.execute(
            sa.text(
                """
                INSERT INTO topics (
                    id, slug, display_name, kind, source, description, parent_topic_id
                )
                SELECT
                    CAST(:topic_id AS uuid), :slug, :display_name, 'research_subaxis',
                    'local_taxonomy', 'Heuristic sub-area used to audit coverage; not an author-reported label.', id
                FROM topics
                WHERE slug = :parent_slug
                ON CONFLICT (slug) DO UPDATE SET parent_topic_id = EXCLUDED.parent_topic_id
                """
            ).bindparams(
                topic_id=topic_id,
                slug=slug,
                display_name=display_name,
                parent_slug=parent_slug,
            )
        )


def downgrade() -> None:
    op.drop_table("research_opportunities")
    op.drop_index("ix_daily_discovery_events_date", table_name="daily_discovery_events")
    op.drop_table("daily_discovery_events")
    op.drop_index("ix_paper_localizations_paper", table_name="paper_localizations")
    op.drop_table("paper_localizations")
    op.drop_index("ix_full_text_queue_priority", table_name="full_text_queue")
    op.drop_table("full_text_queue")
    op.drop_table("paper_content_profiles")
    op.drop_index("ix_topics_parent_topic_id", table_name="topics")
    op.drop_constraint("fk_topics_parent_topic_id", "topics", type_="foreignkey")
    op.drop_column("topics", "parent_topic_id")
