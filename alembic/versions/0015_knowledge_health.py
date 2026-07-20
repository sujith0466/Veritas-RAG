"""knowledge_health

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-20 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0015'
down_revision: Union[str, None] = '0014'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table('health_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('health_score', sa.Float(), nullable=False),
        sa.Column('issues_found_count', sa.Integer(), nullable=False),
        sa.Column('metadata_payload', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_health_logs_tenant_id'), 'health_logs', ['tenant_id'], unique=False)
    
    op.create_table('quarantine_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_id', sa.String(length=128), nullable=False),
        sa.Column('action', sa.String(length=32), nullable=False),
        sa.Column('reason', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_quarantine_logs_document_id'), 'quarantine_logs', ['document_id'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_quarantine_logs_document_id'), table_name='quarantine_logs')
    op.drop_table('quarantine_logs')
    op.drop_index(op.f('ix_health_logs_tenant_id'), table_name='health_logs')
    op.drop_table('health_logs')
