"""Create hybrid retrieval schema: retrieval_queries.

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-19 10:00:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "retrieval_queries",
        sa.Column("tenant_id", sa.String(length=100), nullable=False),
        sa.Column("correlation_id", sa.String(length=100), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("dense_candidate_count", sa.Integer(), nullable=False),
        sa.Column("sparse_candidate_count", sa.Integer(), nullable=False),
        sa.Column("merged_unique_count", sa.Integer(), nullable=False),
        sa.Column("final_top_k", sa.Integer(), nullable=False),
        sa.Column("total_duration_ms", sa.Float(), nullable=False),
        sa.Column("stage_breakdown_json", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_retrieval_queries_tenant_created_idx", "retrieval_queries", ["tenant_id", "created_at"])
    op.create_index("ix_retrieval_queries_tenant_corr_idx", "retrieval_queries", ["tenant_id", "correlation_id"])
    op.create_index(op.f("ix_retrieval_queries_tenant_id"), "retrieval_queries", ["tenant_id"])
    op.create_index(op.f("ix_retrieval_queries_correlation_id"), "retrieval_queries", ["correlation_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_retrieval_queries_correlation_id"), table_name="retrieval_queries")
    op.drop_index(op.f("ix_retrieval_queries_tenant_id"), table_name="retrieval_queries")
    op.drop_index("ix_retrieval_queries_tenant_corr_idx", table_name="retrieval_queries")
    op.drop_index("ix_retrieval_queries_tenant_created_idx", table_name="retrieval_queries")
    op.drop_table("retrieval_queries")
