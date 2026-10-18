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
    pass


def downgrade() -> None:
    pass

