"""migrate_user_role_to_viewer

Revision ID: 113748cb0671
Revises: 20260805_095756_add_vector_reindex_job
Create Date: 2026-08-07 09:45:18.294406+00:00

"""
from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '113748cb0671'
down_revision: Union[str, None] = '20260805095756'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update existing 'user' roles to 'viewer'
    op.execute("UPDATE users SET role = 'viewer' WHERE role = 'user'")

def downgrade() -> None:
    # Revert 'viewer' back to 'user' for those converted
    # Note: this might convert users who were genuinely intended to be 'viewer'
    op.execute("UPDATE users SET role = 'user' WHERE role = 'viewer'")
