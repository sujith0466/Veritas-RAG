"""f4_2_f4_3_f4_4_membership_and_rbac

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-02 15:10:00.000000+00:00

"""
from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns to workspace_members
    op.add_column('workspace_members', sa.Column('status', sa.String(length=50), nullable=False, server_default='ACTIVE'))
    op.add_column('workspace_members', sa.Column('last_active_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('workspace_members', sa.Column('member_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('workspace_members', sa.Column('invited_by_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True))
    op.add_column('workspace_members', sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.text("(now() AT TIME ZONE 'UTC')"), nullable=False))
    op.add_column('workspace_members', sa.Column('version', sa.Integer(), nullable=False, server_default='1'))

    # Indexes
    op.create_index(
        'idx_workspace_members_workspace_status',
        'workspace_members',
        ['workspace_id', 'status'],
        postgresql_where=sa.text('is_deleted = false')
    )
    op.create_index(
        'idx_workspace_members_workspace_role',
        'workspace_members',
        ['workspace_id', 'role'],
        postgresql_where=sa.text('is_deleted = false')
    )
    op.create_index(
        'idx_workspace_members_keyset',
        'workspace_members',
        ['workspace_id', 'created_at', 'id'],
        postgresql_where=sa.text('is_deleted = false')
    )
    op.create_index(
        'uq_workspace_members_active_user',
        'workspace_members',
        ['workspace_id', 'user_id'],
        unique=True,
        postgresql_where=sa.text('is_deleted = false')
    )


def downgrade() -> None:
    op.drop_index('uq_workspace_members_active_user', table_name='workspace_members')
    op.drop_index('idx_workspace_members_keyset', table_name='workspace_members')
    op.drop_index('idx_workspace_members_workspace_role', table_name='workspace_members')
    op.drop_index('idx_workspace_members_workspace_status', table_name='workspace_members')

    op.drop_column('workspace_members', 'version')
    op.drop_column('workspace_members', 'joined_at')
    op.drop_column('workspace_members', 'invited_by_user_id')
    op.drop_column('workspace_members', 'member_metadata')
    op.drop_column('workspace_members', 'last_active_at')
    op.drop_column('workspace_members', 'status')
