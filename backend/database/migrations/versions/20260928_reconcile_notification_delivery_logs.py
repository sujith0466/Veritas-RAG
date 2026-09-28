"""Reconcile notification_delivery_logs schema with ORM model.

Revision ID: chat_001_notif_logs
Revises: e15_iss004_policies
Create Date: 2026-09-28 11:20:00.000000+00:00

"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "chat_001_notif_logs"
down_revision: Union[str, None] = "e15_iss004_policies"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add missing modern columns expected by ORM BaseModel & NotificationDeliveryLog
    op.add_column(
        "notification_delivery_logs",
        sa.Column(
            "payload_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "notification_delivery_logs",
        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "notification_delivery_logs",
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # 2. Drop legacy unused columns
    op.drop_column("notification_delivery_logs", "notification_id")
    op.drop_column("notification_delivery_logs", "retry_count")


def downgrade() -> None:
    # 1. Restore legacy columns
    op.add_column(
        "notification_delivery_logs",
        sa.Column(
            "notification_id",
            sa.UUID(),
            autoincrement=False,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
    )
    op.add_column(
        "notification_delivery_logs",
        sa.Column(
            "retry_count",
            sa.INTEGER(),
            autoincrement=False,
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    # 2. Drop modern columns
    op.drop_column("notification_delivery_logs", "is_deleted")
    op.drop_column("notification_delivery_logs", "attempt_count")
    op.drop_column("notification_delivery_logs", "payload_snapshot")
