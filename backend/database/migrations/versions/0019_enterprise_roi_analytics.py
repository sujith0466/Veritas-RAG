"""enterprise roi analytics schema

Revision ID: 0019
Revises: 0018
Create Date: 2026-07-20 12:00:00.000000

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_quotas",
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("monthly_token_limit", sa.BigInteger(), nullable=False),
        sa.Column("monthly_budget_usd", sa.Float(), nullable=False),
        sa.Column("warning_threshold_pct", sa.Float(), nullable=False),
        sa.Column("is_hard_enforced", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("tenant_id"),
    )

    op.create_table(
        "token_usages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("total_cost_usd", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_token_usages_correlation_id"),
        "token_usages",
        ["correlation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_token_usages_tenant_id"), "token_usages", ["tenant_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_token_usages_tenant_id"), table_name="token_usages")
    op.drop_index(op.f("ix_token_usages_correlation_id"), table_name="token_usages")
    op.drop_table("token_usages")
    op.drop_table("tenant_quotas")
