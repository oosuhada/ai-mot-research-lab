"""Add compact graph-derived features for PostgreSQL GraphRAG fallback.

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | Sequence[str] | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "paper_graph_features",
        sa.Column("paper_id", sa.Uuid(), sa.ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("citation_pagerank", sa.Float(), nullable=False, server_default="0"),
        sa.Column("citation_community", sa.BigInteger()),
        sa.Column("source_projection_id", sa.String(length=128), nullable=False, server_default="neo4j-prototype"),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_paper_graph_features_community", "paper_graph_features", ["citation_community"])
    op.create_index("ix_paper_graph_features_pagerank", "paper_graph_features", ["citation_pagerank"])

    op.create_table(
        "paper_graph_neighbors",
        sa.Column("seed_paper_id", sa.Uuid(), sa.ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("neighbor_paper_id", sa.Uuid(), sa.ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("relation", sa.String(length=32), primary_key=True),
        sa.Column("distance", sa.Integer()),
        sa.Column("weight", sa.Float(), nullable=False, server_default="0"),
        sa.Column("citation_paths", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("shared_topics", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("shared_authors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("shared_institutions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("same_community", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source_projection_id", sa.String(length=128), nullable=False, server_default="neo4j-prototype"),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "relation IN ('citation','topic','author','institution','community')",
            name="ck_paper_graph_neighbors_relation",
        ),
        sa.CheckConstraint("seed_paper_id <> neighbor_paper_id", name="ck_paper_graph_neighbors_not_self"),
    )
    op.create_index("ix_paper_graph_neighbors_seed_weight", "paper_graph_neighbors", ["seed_paper_id", "weight"])
    op.create_index("ix_paper_graph_neighbors_neighbor", "paper_graph_neighbors", ["neighbor_paper_id"])
    op.create_index("ix_paper_graph_neighbors_relation", "paper_graph_neighbors", ["relation"])


def downgrade() -> None:
    op.drop_index("ix_paper_graph_neighbors_relation", table_name="paper_graph_neighbors")
    op.drop_index("ix_paper_graph_neighbors_neighbor", table_name="paper_graph_neighbors")
    op.drop_index("ix_paper_graph_neighbors_seed_weight", table_name="paper_graph_neighbors")
    op.drop_table("paper_graph_neighbors")
    op.drop_index("ix_paper_graph_features_pagerank", table_name="paper_graph_features")
    op.drop_index("ix_paper_graph_features_community", table_name="paper_graph_features")
    op.drop_table("paper_graph_features")
