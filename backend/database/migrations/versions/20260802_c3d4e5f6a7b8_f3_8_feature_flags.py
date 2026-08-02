"""f3_8_feature_flags

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-02 09:35:00.000000+00:00

"""
from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Master Feature Flags table
    op.create_table(
        'feature_flags',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('key', sa.String(length=100), nullable=False, unique=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.String(length=1024), nullable=True),
        sa.Column('category', sa.String(length=50), nullable=False, server_default='SYSTEM'),
        sa.Column('lifecycle_state', sa.String(length=50), nullable=False, server_default='DRAFT'),
        sa.Column('flag_type', sa.String(length=50), nullable=False, server_default='BOOLEAN'),
        sa.Column('default_enabled', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('is_killswitch_active', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('prerequisite_flag_keys', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('default_variant_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('target_environments', sa.String(length=255), nullable=False, server_default='production,staging,development'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )
    op.create_index('ix_feature_flags_key', 'feature_flags', ['key'], unique=True)
    op.create_index('ix_feature_flags_category', 'feature_flags', ['category'], unique=False)

    # 2. Workspace Override Rules table
    op.create_table(
        'feature_flag_workspace_rules',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('flag_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('rollout_percentage', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('activation_start_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('activation_end_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('targeting_conditions_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('custom_variant_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.ForeignKeyConstraint(['flag_id'], ['feature_flags.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('flag_id', 'workspace_id', name='uq_flag_workspace'),
        sa.CheckConstraint('rollout_percentage >= 0 AND rollout_percentage <= 100', name='chk_rollout_percentage'),
    )
    op.create_index('ix_ff_ws_rules_workspace', 'feature_flag_workspace_rules', ['workspace_id'], unique=False)

    # 3. Enhanced Audit History Snapshots table
    op.create_table(
        'feature_flag_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('flag_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('changed_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('change_action', sa.String(length=50), nullable=False),
        sa.Column('change_reason', sa.String(length=255), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=512), nullable=True),
        sa.Column('old_rule_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('new_rule_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.ForeignKeyConstraint(['flag_id'], ['feature_flags.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['changed_by_user_id'], ['users.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_ff_history_flag_ws', 'feature_flag_history', ['flag_id', 'workspace_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_ff_history_flag_ws', table_name='feature_flag_history')
    op.drop_table('feature_flag_history')
    op.drop_index('ix_ff_ws_rules_workspace', table_name='feature_flag_workspace_rules')
    op.drop_table('feature_flag_workspace_rules')
    op.drop_index('ix_feature_flags_category', table_name='feature_flags')
    op.drop_index('ix_feature_flags_key', table_name='feature_flags')
    op.drop_table('feature_flags')
