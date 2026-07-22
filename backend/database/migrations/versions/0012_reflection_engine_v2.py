"""reflection_engine_v2

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-20 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reflection_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("overall_verdict", sa.String(length=32), nullable=False),
        sa.Column("hallucination_score", sa.Float(), nullable=False),
        sa.Column("completeness_score", sa.Float(), nullable=False),
        sa.Column("consistency_score", sa.Float(), nullable=False),
        sa.Column("is_safe_to_serve", sa.Boolean(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("metadata_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_reflection_logs_correlation_id"),
        "reflection_logs",
        ["correlation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reflection_logs_tenant_id"),
        "reflection_logs",
        ["tenant_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_reflection_logs_tenant_id"), table_name="reflection_logs")
    op.drop_index(
        op.f("ix_reflection_logs_correlation_id"), table_name="reflection_logs"
    )
    op.drop_table("reflection_logs")
