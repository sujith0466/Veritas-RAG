"""f4_1_workspace_invitations

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-08-02 14:45:00.000000+00:00

"""
from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'workspace_invitations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='PENDING'),
        sa.Column('invited_by_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_by_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('resend_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_resent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("(now() AT TIME ZONE 'UTC')"), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text("(now() AT TIME ZONE 'UTC')"), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
    )

    op.create_index(
        'uq_workspace_invitations_token_hash',
        'workspace_invitations',
        ['token_hash'],
        unique=True,
        postgresql_where=sa.text('is_deleted = false')
    )
    op.create_index(
        'uq_workspace_invitations_active_email',
        'workspace_invitations',
        ['workspace_id', sa.text('LOWER(email)')],
        unique=True,
        postgresql_where=sa.text("status = 'PENDING' AND is_deleted = false")
    )
    op.create_index(
        'idx_workspace_invitations_workspace_status_created',
        'workspace_invitations',
        ['workspace_id', 'status', 'created_at'],
        postgresql_where=sa.text('is_deleted = false')
    )
    op.create_index(
        'idx_workspace_invitations_pending_expiry',
        'workspace_invitations',
        ['status', 'expires_at'],
        postgresql_where=sa.text("status = 'PENDING' AND is_deleted = false")
    )


def downgrade() -> None:
    op.drop_index('idx_workspace_invitations_pending_expiry', table_name='workspace_invitations')
    op.drop_index('idx_workspace_invitations_workspace_status_created', table_name='workspace_invitations')
    op.drop_index('uq_workspace_invitations_active_email', table_name='workspace_invitations')
    op.drop_index('uq_workspace_invitations_token_hash', table_name='workspace_invitations')
    op.drop_table('workspace_invitations')
