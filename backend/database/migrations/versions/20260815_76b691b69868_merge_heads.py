"""merge heads

Revision ID: 76b691b69868
Revises: 2533885a5f0a, 8b1a3d92e5f1
Create Date: 2026-08-15 09:13:27.468245+00:00

"""
from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '76b691b69868'
down_revision: Union[str, None] = ('2533885a5f0a', '8b1a3d92e5f1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
