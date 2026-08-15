"""epic12_audit_tenant_id

Revision ID: 8b1a3d92e5f1
Revises: 6c11701a28c5
Create Date: 2026-08-15 13:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '8b1a3d92e5f1'
down_revision: Union[str, None] = '6c11701a28c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add the tenant_id column allowing nulls first to handle existing data
    op.add_column('audit_logs', sa.Column('tenant_id', sa.UUID(), nullable=True))
    op.create_index(op.f('ix_audit_logs_tenant_id'), 'audit_logs', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_audit_logs_tenant_id'), table_name='audit_logs')
    op.drop_column('audit_logs', 'tenant_id')
