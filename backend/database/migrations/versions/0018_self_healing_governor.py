"""self healing governor schema

Revision ID: 0018
Revises: 0017
Create Date: 2026-07-20 11:00:00.000000

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "self_healing_policies",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("auto_parameter_tuning", sa.Boolean(), nullable=False),
        sa.Column("auto_model_rotation", sa.Boolean(), nullable=False),
        sa.Column("auto_quarantine_sweep", sa.Boolean(), nullable=False),
        sa.Column("max_interventions_per_hour", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_self_healing_policies_tenant_id"),
        "self_healing_policies",
        ["tenant_id"],
        unique=False,
    )

    op.create_table(
        "healing_actions_log",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("trigger_reason", sa.Text(), nullable=False),
        sa.Column(
            "changes_applied", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("is_rolled_back", sa.Boolean(), nullable=False),
        sa.Column(
            "executed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_healing_actions_log_tenant_id"),
        "healing_actions_log",
        ["tenant_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_healing_actions_log_tenant_id"), table_name="healing_actions_log"
    )
    op.drop_table("healing_actions_log")
    op.drop_index(
        op.f("ix_self_healing_policies_tenant_id"), table_name="self_healing_policies"
    )
    op.drop_table("self_healing_policies")
