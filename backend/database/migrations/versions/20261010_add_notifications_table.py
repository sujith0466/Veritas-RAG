"""Add persistent in-app notifications table.

Revision ID: notif_01_in_app_notifications
Revises: ws_c1_workspace_access_requests
Create Date: 2026-10-10 12:00:00.000000+00:00

"""

from collections.abc import Sequence
from typing import Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "notif_01_in_app_notifications"
down_revision: Union[str, None] = "ws_c1_workspace_access_requests"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table("notifications"):
        op.create_table(
            "notifications",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                default=uuid.uuid4,
            ),
            sa.Column(
                "tenant_id",
                postgresql.UUID(as_uuid=True),
                nullable=False,
            ),
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=True,
            ),
            sa.Column(
                "category",
                sa.String(50),
                nullable=False,
                server_default="SYSTEM",
            ),
            sa.Column(
                "severity",
                sa.String(50),
                nullable=False,
                server_default="INFO",
            ),
            sa.Column(
                "title",
                sa.String(255),
                nullable=False,
            ),
            sa.Column(
                "message",
                sa.Text(),
                nullable=False,
            ),
            sa.Column(
                "action_url",
                sa.String(512),
                nullable=True,
            ),
            sa.Column(
                "payload_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
            ),
            sa.Column(
                "is_read",
                sa.Boolean(),
                nullable=False,
                server_default="false",
            ),
            sa.Column(
                "read_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
            sa.Column(
                "is_deleted",
                sa.Boolean(),
                nullable=False,
                server_default="false",
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )

        op.create_index(
            op.f("ix_notifications_tenant_id"),
            "notifications",
            ["tenant_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_notifications_user_id"),
            "notifications",
            ["user_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_notifications_is_read"),
            "notifications",
            ["is_read"],
            unique=False,
        )
        op.create_index(
            "ix_notifications_tenant_user_read_created",
            "notifications",
            ["tenant_id", "user_id", "is_read", "created_at"],
            unique=False,
        )
        op.create_index(
            "ix_notifications_tenant_created",
            "notifications",
            ["tenant_id", "created_at"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if insp.has_table("notifications"):
        op.drop_index("ix_notifications_tenant_created", table_name="notifications")
        op.drop_index("ix_notifications_tenant_user_read_created", table_name="notifications")
        op.drop_index(op.f("ix_notifications_is_read"), table_name="notifications")
        op.drop_index(op.f("ix_notifications_user_id"), table_name="notifications")
        op.drop_index(op.f("ix_notifications_tenant_id"), table_name="notifications")
        op.drop_table("notifications")
