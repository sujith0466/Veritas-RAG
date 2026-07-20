"""production hardening schema

Revision ID: 0020
Revises: 0019
Create Date: 2026-07-20 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '0020'
down_revision = '0019'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table('fault_policies',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('chaos_token', sa.String(length=128), nullable=False),
        sa.Column('fault_type', sa.String(length=64), nullable=False),
        sa.Column('target_provider', sa.String(length=64), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=False),
        sa.Column('error_rate_pct', sa.Float(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_fault_policies_chaos_token'), 'fault_policies', ['chaos_token'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_fault_policies_chaos_token'), table_name='fault_policies')
    op.drop_table('fault_policies')
