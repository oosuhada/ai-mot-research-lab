"""Add Korean localization full-text search indexes.

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-24
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE paper_localizations
        ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (
          setweight(to_tsvector('simple', coalesce(title, '')), 'A') ||
          setweight(to_tsvector('simple', coalesce(abstract, '')), 'B')
        ) STORED
        """
    )
    op.execute(
        "CREATE INDEX ix_paper_localizations_search_vector "
        "ON paper_localizations USING gin (search_vector) WHERE status = 'completed'"
    )
    op.execute(
        "CREATE INDEX ix_paper_localizations_title_search_vector ON paper_localizations "
        "USING gin (to_tsvector('simple', coalesce(title, ''))) WHERE status = 'completed'"
    )
    op.execute(
        "CREATE INDEX ix_paper_localizations_abstract_search_vector ON paper_localizations "
        "USING gin (to_tsvector('simple', coalesce(abstract, ''))) WHERE status = 'completed'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_paper_localizations_abstract_search_vector")
    op.execute("DROP INDEX IF EXISTS ix_paper_localizations_title_search_vector")
    op.execute("DROP INDEX IF EXISTS ix_paper_localizations_search_vector")
    op.execute("ALTER TABLE paper_localizations DROP COLUMN IF EXISTS search_vector")
