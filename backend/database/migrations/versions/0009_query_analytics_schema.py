"""Create query_analytics_records table.

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-20 01:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "query_analytics_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=100), nullable=False),
        sa.Column("correlation_id", sa.String(length=100), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("outcome", sa.String(length=50), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("hallucination_score", sa.Float(), nullable=True),
        sa.Column("reliability_score", sa.Float(), nullable=True),
        sa.Column("retry_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_duration_ms", sa.Float(), nullable=False),
        sa.Column(
            "is_safe_to_serve",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_query_analytics_records")),
    )
    op.create_index(
        op.f("ix_query_analytics_tenant_id"),
        "query_analytics_records",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_query_analytics_tenant_created_idx",
        "query_analytics_records",
        ["tenant_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_query_analytics_tenant_outcome_idx",
        "query_analytics_records",
        ["tenant_id", "outcome"],
        unique=False,
    )
    op.create_index(
        "ix_query_analytics_corr_idx",
        "query_analytics_records",
        ["correlation_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("query_analytics_records")
