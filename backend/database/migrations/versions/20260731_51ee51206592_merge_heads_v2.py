"""merge_heads_v2

Revision ID: 51ee51206592
Revises: 0022, 5de17c10bdc3
Create Date: 2026-07-31 02:31:49.606366+00:00

"""
from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '51ee51206592'
down_revision: Union[str, None] = ('0022', '5de17c10bdc3')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
