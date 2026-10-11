"""Add encrypted_secret to workspace_webhooks and webhook_id index to logs.

Revision ID: wh_01_webhook_crypto
Revises: notif_01_in_app_notifications
Create Date: 2026-10-11 12:00:00.000000+00:00

"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "wh_01_webhook_crypto"
down_revision: Union[str, None] = "notif_01_in_app_notifications"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # 1. Add encrypted_secret column to workspace_webhooks if not present
    columns = [c["name"] for c in insp.get_columns("workspace_webhooks")]
    if "encrypted_secret" not in columns:
        op.add_column(
            "workspace_webhooks",
            sa.Column("encrypted_secret", sa.Text(), nullable=True),
        )

    # 2. Add composite index on notification_delivery_logs for tenant/type/created_at
    indexes = [idx["name"] for idx in insp.get_indexes("notification_delivery_logs")]
    if "ix_notif_logs_tenant_type_created" not in indexes:
        op.create_index(
            "ix_notif_logs_tenant_type_created",
            "notification_delivery_logs",
            ["tenant_id", "type", "created_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    indexes = [idx["name"] for idx in insp.get_indexes("notification_delivery_logs")]
    if "ix_notif_logs_tenant_type_created" in indexes:
        op.drop_index("ix_notif_logs_tenant_type_created", table_name="notification_delivery_logs")

    columns = [c["name"] for c in insp.get_columns("workspace_webhooks")]
    if "encrypted_secret" in columns:
        op.drop_column("workspace_webhooks", "encrypted_secret")
