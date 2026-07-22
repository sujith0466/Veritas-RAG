"""alerting engine schema

Revision ID: 0017
Revises: 0016
Create Date: 2026-07-20 10:00:00.000000

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alert_rules",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("metric_name", sa.String(length=64), nullable=False),
        sa.Column("operator", sa.String(length=32), nullable=False),
        sa.Column("threshold_value", sa.String(length=128), nullable=False),
        sa.Column(
            "channels_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("cooldown_minutes", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_alert_rules_tenant_id"), "alert_rules", ["tenant_id"], unique=False
    )

    op.create_table(
        "alert_history",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("rule_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("channel_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "payload_sent", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "triggered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["rule_id"],
            ["alert_rules.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_alert_history_tenant_id"), "alert_history", ["tenant_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_alert_history_tenant_id"), table_name="alert_history")
    op.drop_table("alert_history")
    op.drop_index(op.f("ix_alert_rules_tenant_id"), table_name="alert_rules")
    op.drop_table("alert_rules")
