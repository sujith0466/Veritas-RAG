"""add workspace_name

Revision ID: 42e18ea087d3
Revises: 76b691b69868
Create Date: 2026-08-18 03:14:30.675623+00:00

"""
from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '42e18ea087d3'
down_revision: Union[str, None] = '76b691b69868'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
