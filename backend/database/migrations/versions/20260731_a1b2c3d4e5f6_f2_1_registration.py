"""Add F2.1 Registration Fields

Revision ID: a1b2c3d4e5f6
Revises: fb640fe318ec
Create Date: 2026-07-31 15:30:00.000000

"""
from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'fb640fe318ec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('hashed_password', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('verification_token_hash', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('verification_token_expires_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_users_verification_token_hash'), 'users', ['verification_token_hash'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_users_verification_token_hash'), table_name='users')
    op.drop_column('users', 'last_login_at')
    op.drop_column('users', 'verification_token_expires_at')
    op.drop_column('users', 'verification_token_hash')
    op.drop_column('users', 'verified_at')
    op.drop_column('users', 'is_verified')
    op.drop_column('users', 'hashed_password')
