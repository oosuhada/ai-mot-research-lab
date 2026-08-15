"""Add PostgreSQL search acceleration and query observability foundations.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-24
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    # Creating the extension is safe here. Collection begins only when the host also
    # preloads pg_stat_statements; deployment.md documents that one-time restart.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_stat_statements")

    op.execute("ALTER TABLE paper_chunks ADD COLUMN embedding_provider varchar(64)")
    op.execute("ALTER TABLE paper_chunks ADD COLUMN embedding_model varchar(128)")
    op.execute(
        "UPDATE paper_chunks SET embedding_provider = 'local_hash', embedding_model = 'token-hash-v1' "
        "WHERE embedding IS NOT NULL"
    )

    op.execute(
        """
        ALTER TABLE paper_chunks
        ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (to_tsvector('simple', coalesce(text, ''))) STORED
        """
    )
    op.execute("CREATE INDEX ix_paper_chunks_search_vector ON paper_chunks USING gin (search_vector)")
    op.execute(
        "CREATE INDEX ix_papers_title_search_vector ON papers "
        "USING gin (to_tsvector('simple', coalesce(title, '')))"
    )
    op.execute(
        "CREATE INDEX ix_papers_abstract_search_vector ON papers "
        "USING gin (to_tsvector('simple', coalesce(abstract, '')))"
    )
    op.execute("CREATE INDEX ix_authors_display_name_trgm ON authors USING gin (display_name gin_trgm_ops)")
    op.execute("CREATE INDEX ix_venues_name_trgm ON venues USING gin (name gin_trgm_ops)")
    op.execute("CREATE INDEX ix_tags_name_trgm ON tags USING gin (name gin_trgm_ops)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_tags_name_trgm")
    op.execute("DROP INDEX IF EXISTS ix_venues_name_trgm")
    op.execute("DROP INDEX IF EXISTS ix_authors_display_name_trgm")
    op.execute("DROP INDEX IF EXISTS ix_papers_abstract_search_vector")
    op.execute("DROP INDEX IF EXISTS ix_papers_title_search_vector")
    op.execute("DROP INDEX IF EXISTS ix_paper_chunks_search_vector")
    op.execute("ALTER TABLE paper_chunks DROP COLUMN IF EXISTS search_vector")
    op.execute("ALTER TABLE paper_chunks DROP COLUMN IF EXISTS embedding_model")
    op.execute("ALTER TABLE paper_chunks DROP COLUMN IF EXISTS embedding_provider")
    # Extensions may be shared with other applications in the same database; do not
    # remove them during an application downgrade.
