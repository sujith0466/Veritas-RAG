"""Add Workspace Domains and Identity Providers

Revision ID: c722fc06aec0
Revises: 2e2423fb5e1b
Create Date: 2026-08-02 10:23:24.427592+00:00

"""
from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c722fc06aec0'
down_revision: Union[str, None] = '2e2423fb5e1b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # workspace_domains
    op.create_table(
        'workspace_domains',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('workspace_id', sa.UUID(), nullable=False),
        sa.Column('domain_name', sa.String(length=255), nullable=False),
        sa.Column('verification_token_hash', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('is_primary', sa.Boolean(), server_default='false', nullable=True),
        sa.Column('last_verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('token_expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('dns_last_checked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_reason', sa.Text(), nullable=True),
        sa.Column('version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('verification_token_hash')
    )
    op.create_index(
        'ix_workspace_domains_domain',
        'workspace_domains',
        ['domain_name'],
        unique=True,
        postgresql_where=sa.text("status IN ('VERIFIED')")
    )
    op.create_index('ix_workspace_domains_workspace_id', 'workspace_domains', ['workspace_id'], unique=False)

    # domain_cooldowns
    op.create_table(
        'domain_cooldowns',
        sa.Column('domain_name', sa.String(length=255), nullable=False),
        sa.Column('released_by_workspace_id', sa.UUID(), nullable=False),
        sa.Column('cooldown_expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['released_by_workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('domain_name')
    )

    # identity_providers
    op.create_table(
        'identity_providers',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('workspace_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=True),
        sa.Column('entity_id_issuer', sa.String(length=255), nullable=False),
        sa.Column('sso_url', sa.String(length=2048), nullable=False),
        sa.Column('logout_url', sa.String(length=2048), nullable=True),
        sa.Column('metadata_url', sa.String(length=2048), nullable=True),
        sa.Column('certificates', sa.JSON(), nullable=True),
        sa.Column('attribute_mapping', sa.JSON(), nullable=False),
        sa.Column('domain_restrictions', sa.ARRAY(sa.String()), nullable=True),
        sa.Column('jit_enabled', sa.Boolean(), server_default='false', nullable=True),
        sa.Column('force_sso', sa.Boolean(), server_default='false', nullable=True),
        sa.Column('version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_identity_providers_workspace_id', 'identity_providers', ['workspace_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_identity_providers_workspace_id', table_name='identity_providers')
    op.drop_table('identity_providers')
    op.drop_table('domain_cooldowns')
    op.drop_index('ix_workspace_domains_workspace_id', table_name='workspace_domains')
    op.drop_index('ix_workspace_domains_domain', table_name='workspace_domains')
    op.drop_table('workspace_domains')
