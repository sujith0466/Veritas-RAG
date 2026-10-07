"""Add workspace_access_requests table.

Revision ID: ws_c1_workspace_access_requests
Revises: ws_b6_user_quotas
Create Date: 2026-10-07 08:00:00.000000+00:00

"""

from collections.abc import Sequence
from typing import Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "ws_c1_workspace_access_requests"
down_revision: Union[str, None] = "ws_b6_user_quotas"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table("workspace_access_requests"):
        op.create_table(
            "workspace_access_requests",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
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
            sa.Column("request_type", sa.String(32), nullable=False, server_default="ROLE_ELEVATION"),
            sa.Column("current_role", sa.String(32), nullable=True),
            sa.Column("requested_role", sa.String(32), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column(
                "reviewed_by_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("rejection_reason", sa.Text(), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
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
        )

        op.create_index(
            "ix_workspace_access_requests_workspace_id",
            "workspace_access_requests",
            ["workspace_id"],
        )
        op.create_index(
            "ix_workspace_access_requests_user_id",
            "workspace_access_requests",
            ["user_id"],
        )
        op.create_index(
            "ix_workspace_access_requests_workspace_status",
            "workspace_access_requests",
            ["workspace_id", "status"],
        )
        op.create_index(
            "uq_active_pending_access_request",
            "workspace_access_requests",
            ["workspace_id", "user_id", "request_type"],
            unique=True,
            postgresql_where=sa.text("status = 'PENDING'"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if insp.has_table("workspace_access_requests"):
        op.drop_index(
            "uq_active_pending_access_request",
            table_name="workspace_access_requests",
        )
        op.drop_index(
            "ix_workspace_access_requests_workspace_status",
            table_name="workspace_access_requests",
        )
        op.drop_index(
            "ix_workspace_access_requests_user_id",
            table_name="workspace_access_requests",
        )
        op.drop_index(
            "ix_workspace_access_requests_workspace_id",
            table_name="workspace_access_requests",
        )
        op.drop_table("workspace_access_requests")
