"""confidence_engine_v2

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-20

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "confidence_evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", sa.String(50), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("coverage_score", sa.Float(), nullable=False),
        sa.Column("strength_score", sa.Float(), nullable=False),
        sa.Column("freshness_score", sa.Float(), nullable=False),
        sa.Column("conflict_score", sa.Float(), nullable=False),
        sa.Column("is_degraded", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_confidence_evaluations_tenant_id", "confidence_evaluations", ["tenant_id"]
    )


def downgrade():
    op.drop_table("confidence_evaluations")
