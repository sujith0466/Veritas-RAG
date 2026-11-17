"""WP-9 user-scoped notifications nullable tenant_id migration

Revision ID: 20261116_wp9_user_scoped_notifications
Revises: 20261116_sec7_batch3_compatibility
Create Date: 2026-11-16 12:15:00.000000

VRAG-AUTH-SEC8-10-IMPLEMENTATION-20261116-01 / D-20 Option A:
- Allow notifications.tenant_id to be NULL for user-scoped notifications
  (e.g., workspace member removal and suspension notifications where workspace
   membership is severed and the notification belongs to the personal user feed).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20261116_wp9_user_scoped_notifications"
down_revision = "20261116_sec7_batch3_compatibility"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "notifications",
        "tenant_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )


def downgrade() -> None:
    # Update any null tenant_id to nil uuid before restoring NOT NULL constraint
    op.execute(
        "UPDATE notifications SET tenant_id = '00000000-0000-0000-0000-000000000000' WHERE tenant_id IS NULL"
    )
    op.alter_column(
        "notifications",
        "tenant_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
