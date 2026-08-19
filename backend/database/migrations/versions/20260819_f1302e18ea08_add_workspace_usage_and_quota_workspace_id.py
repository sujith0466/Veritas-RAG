"""add workspace_usage and quota workspace_id

Revision ID: f1302e18ea08
Revises: 42e18ea087d3
Create Date: 2026-08-19 02:00:00.000000+00:00

"""
from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1302e18ea08'
down_revision: Union[str, None] = '42e18ea087d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'workspace_usages',
        sa.Column('workspace_id', sa.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('billing_period_start', sa.Date(), nullable=False),
        sa.Column('used_tokens', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('used_queries', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('workspace_id', 'billing_period_start', name='pk_workspace_usages'),
        sa.CheckConstraint('used_tokens >= 0', name='chk_workspace_usages_tokens_positive'),
        sa.CheckConstraint('used_queries >= 0', name='chk_workspace_usages_queries_positive'),
    )

    op.add_column(
        'tenant_quotas',
        sa.Column('workspace_id', sa.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='SET NULL'), nullable=True)
    )
    op.create_index('ix_tenant_quotas_workspace_id', 'tenant_quotas', ['workspace_id'])


def downgrade() -> None:
    op.drop_index('ix_tenant_quotas_workspace_id', table_name='tenant_quotas')
    op.drop_column('tenant_quotas', 'workspace_id')
    op.drop_table('workspace_usages')
