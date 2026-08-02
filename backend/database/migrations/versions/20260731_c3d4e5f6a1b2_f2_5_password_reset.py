"""F2.5 Password Reset fields

Revision ID: c3d4e5f6a1b2
Revises: f2b3c4d5e6f7
Create Date: 2026-07-31 15:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a1b2'
down_revision: Union[str, None] = 'f2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns for F2.5 Password Reset
    op.add_column('users', sa.Column('password_reset_token_hash', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('password_reset_token_expires_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('password_changed_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_users_password_reset_token_hash'), 'users', ['password_reset_token_hash'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_users_password_reset_token_hash'), table_name='users')
    op.drop_column('users', 'password_changed_at')
    op.drop_column('users', 'password_reset_token_expires_at')
    op.drop_column('users', 'password_reset_token_hash')
