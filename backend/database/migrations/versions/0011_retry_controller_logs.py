"""retry_controller_logs_v2

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-20

Adds retry_decision_logs table for Phase 7 audit trail.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "retry_decision_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("query_id", sa.String(100), nullable=False),
        sa.Column("tenant_id", sa.String(50), nullable=False, index=True),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(50), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("backoff_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "is_budget_exhausted", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column(
            "is_monotonic_regression",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column("reason_code", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_retry_decision_logs_query_id", "retry_decision_logs", ["query_id"]
    )
    op.create_index(
        "idx_retry_decision_logs_tenant_action",
        "retry_decision_logs",
        ["tenant_id", "action"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_retry_decision_logs_tenant_action", table_name="retry_decision_logs"
    )
    op.drop_index("idx_retry_decision_logs_query_id", table_name="retry_decision_logs")
    op.drop_table("retry_decision_logs")
