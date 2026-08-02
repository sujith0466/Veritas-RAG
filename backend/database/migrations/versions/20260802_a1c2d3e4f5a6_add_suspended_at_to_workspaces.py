"""add_suspended_at_to_workspaces

Revision ID: a1c2d3e4f5a6
Revises: 3b576b4541f4
Create Date: 2026-08-02 09:10:00.000000+00:00

"""
from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1c2d3e4f5a6'
down_revision: Union[str, None] = '3b576b4541f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('workspaces', sa.Column('suspended_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('workspaces', 'suspended_at')
