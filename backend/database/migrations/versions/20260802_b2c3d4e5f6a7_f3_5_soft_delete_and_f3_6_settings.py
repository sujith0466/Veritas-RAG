"""f3_5_soft_delete_and_f3_6_settings

Revision ID: b2c3d4e5f6a7
Revises: a1c2d3e4f5a6
Create Date: 2026-08-02 09:20:00.000000+00:00

"""
from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # F3.5 Workspace Soft Deletion metadata & timestamps
    op.add_column('workspaces', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('workspaces', sa.Column('purge_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('workspaces', sa.Column('deleted_by_user_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_workspaces_deleted_by_user_id_users', 'workspaces', 'users', ['deleted_by_user_id'], ['id'], ondelete='SET NULL')
    op.add_column('workspaces', sa.Column('deletion_reason_code', sa.String(length=50), nullable=True))
    op.add_column('workspaces', sa.Column('deletion_reason_text', sa.String(length=1024), nullable=True))
    op.create_index('ix_workspaces_purge_at', 'workspaces', ['purge_at'], unique=False)

    # F3.6 Workspace Settings updates
    op.add_column('workspace_settings', sa.Column('version', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('workspace_settings', sa.Column('settings_hash', sa.String(length=64), nullable=False, server_default=''))

    # F3.6 Workspace Settings History table
    op.create_table(
        'workspace_settings_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('settings_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('schema_version', sa.Integer(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('settings_hash', sa.String(length=64), nullable=False),
        sa.Column('changed_by_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('change_reason', sa.String(length=255), nullable=True),
    )
    op.create_index('ix_workspace_settings_history_workspace_id', 'workspace_settings_history', ['workspace_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_workspace_settings_history_workspace_id', table_name='workspace_settings_history')
    op.drop_table('workspace_settings_history')

    op.drop_column('workspace_settings', 'settings_hash')
    op.drop_column('workspace_settings', 'version')

    op.drop_index('ix_workspaces_purge_at', table_name='workspaces')
    op.drop_constraint('fk_workspaces_deleted_by_user_id_users', 'workspaces', type_='foreignkey')
    op.drop_column('workspaces', 'deletion_reason_text')
    op.drop_column('workspaces', 'deletion_reason_code')
    op.drop_column('workspaces', 'deleted_by_user_id')
    op.drop_column('workspaces', 'purge_at')
    op.drop_column('workspaces', 'deleted_at')
