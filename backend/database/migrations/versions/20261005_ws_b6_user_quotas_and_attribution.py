"""Add workspace user quotas, user usage tracking, and attribution columns.

Revision ID: ws_b6_user_quotas_and_attribution
Revises: ws_a4_invitation_selector
Create Date: 2026-10-05 07:00:00.000000+00:00

"""

from collections.abc import Sequence
from typing import Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "ws_b6_user_quotas"
down_revision: Union[str, None] = "ws_a4_invitation_selector"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # 1. token_usages table & user_id/workspace_id attribution
    if not insp.has_table("token_usages"):
        op.create_table(
            "token_usages",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("tenant_id", sa.String(64), index=True, nullable=False),
            sa.Column(
                "workspace_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
                nullable=True,
            ),
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("correlation_id", sa.String(128), index=True, nullable=False),
            sa.Column("provider", sa.String(64), nullable=False),
            sa.Column("model_name", sa.String(128), nullable=False),
            sa.Column("prompt_tokens", sa.Integer(), nullable=False),
            sa.Column("completion_tokens", sa.Integer(), nullable=False),
            sa.Column("total_cost_usd", sa.Float(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
        )
        op.create_index("ix_token_usages_workspace_id", "token_usages", ["workspace_id"])
        op.create_index("ix_token_usages_user_id", "token_usages", ["user_id"])
    else:
        existing_cols = [c["name"] for c in insp.get_columns("token_usages")]
        if "workspace_id" not in existing_cols:
            op.add_column(
                "token_usages",
                sa.Column(
                    "workspace_id",
                    postgresql.UUID(as_uuid=True),
                    sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
                    nullable=True,
                ),
            )
            op.create_index("ix_token_usages_workspace_id", "token_usages", ["workspace_id"])
        if "user_id" not in existing_cols:
            op.add_column(
                "token_usages",
                sa.Column(
                    "user_id",
                    postgresql.UUID(as_uuid=True),
                    sa.ForeignKey("users.id", ondelete="SET NULL"),
                    nullable=True,
                ),
            )
            op.create_index("ix_token_usages_user_id", "token_usages", ["user_id"])

    # 2. Create workspace_user_quotas table
    if not insp.has_table("workspace_user_quotas"):
        op.create_table(
            "workspace_user_quotas",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "workspace_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("monthly_token_budget", sa.BigInteger(), nullable=True),
            sa.Column("warning_threshold_pct", sa.Float(), server_default="0.80", nullable=False),
            sa.Column("is_hard_enforced", sa.Boolean(), server_default="true", nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.UniqueConstraint("workspace_id", "user_id", name="uq_workspace_user_quotas_workspace_user"),
        )
        op.create_index(
            "ix_workspace_user_quotas_workspace_id",
            "workspace_user_quotas",
            ["workspace_id"],
        )
        op.create_index(
            "ix_workspace_user_quotas_user_id",
            "workspace_user_quotas",
            ["user_id"],
        )

    # 3. Create workspace_user_usages table
    if not insp.has_table("workspace_user_usages"):
        op.create_table(
            "workspace_user_usages",
            sa.Column(
                "workspace_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
                primary_key=True,
                nullable=False,
            ),
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                primary_key=True,
                nullable=False,
            ),
            sa.Column("billing_period_start", sa.Date(), primary_key=True, nullable=False),
            sa.Column("used_tokens", sa.BigInteger(), server_default="0", nullable=False),
            sa.Column("used_queries", sa.Integer(), server_default="0", nullable=False),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.CheckConstraint("used_tokens >= 0", name="chk_workspace_user_usages_tokens_positive"),
            sa.CheckConstraint("used_queries >= 0", name="chk_workspace_user_usages_queries_positive"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if insp.has_table("workspace_user_usages"):
        op.drop_table("workspace_user_usages")
    if insp.has_table("workspace_user_quotas"):
        op.drop_index("ix_workspace_user_quotas_user_id", table_name="workspace_user_quotas")
        op.drop_index("ix_workspace_user_quotas_workspace_id", table_name="workspace_user_quotas")
        op.drop_table("workspace_user_quotas")
    if insp.has_table("token_usages"):
        existing_cols = [c["name"] for c in insp.get_columns("token_usages")]
        if "user_id" in existing_cols:
            op.drop_index("ix_token_usages_user_id", table_name="token_usages")
            op.drop_column("token_usages", "user_id")
        if "workspace_id" in existing_cols:
            op.drop_index("ix_token_usages_workspace_id", table_name="token_usages")
            op.drop_column("token_usages", "workspace_id")
