"""Section 7: Batch 1 - Workspace Ownership Transfer Lifecycle

Revision ID: 20261115_sec7_batch1_transfer
Revises: 20261115_sec6_viewer_mig
Create Date: 2026-11-15 14:00:00.000000+00:00

Governed by: Combined Implementation Plan Revision 4.14 (Section 7, Batch 1 - REV5).
Binding Project Owner Policy:
1. Creates workspace_ownership_transfers table with ON DELETE RESTRICT foreign keys
   to guarantee audit and history retention.
2. Partial unique index ensures at most one PENDING nomination per workspace.
3. Fully reversible downgrade.
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20261115_sec7_batch1_transfer'
down_revision: Union[str, None] = '20261115_sec6_viewer_mig'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'workspace_ownership_transfers',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('nominated_by_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('nominee_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='PENDING'),
        sa.Column('rejection_reason', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('clock_timestamp()')),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text("(clock_timestamp() + INTERVAL '7 days')")),
        sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expired_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('PENDING', 'ACCEPTED', 'REJECTED', 'CANCELLED', 'EXPIRED')", name='ck_transfer_status'),
        sa.CheckConstraint('nominated_by_user_id != nominee_user_id', name='ck_transfer_no_self_nomination'),
    )

    # Partial unique index: at most one active pending nomination per workspace
    op.create_index(
        'uq_workspace_ownership_transfers_active_pending',
        'workspace_ownership_transfers',
        ['workspace_id'],
        unique=True,
        postgresql_where=sa.text("status = 'PENDING'")
    )

    # Performance indexes
    op.create_index(
        'ix_workspace_ownership_transfers_nominee_status',
        'workspace_ownership_transfers',
        ['nominee_user_id', 'status']
    )
    op.create_index(
        'ix_workspace_ownership_transfers_expires_pending',
        'workspace_ownership_transfers',
        ['expires_at'],
        postgresql_where=sa.text("status = 'PENDING'")
    )
    op.create_index(
        'ix_workspace_ownership_transfers_workspace_created',
        'workspace_ownership_transfers',
        ['workspace_id', 'created_at']
    )


def downgrade() -> None:
    op.drop_index('ix_workspace_ownership_transfers_workspace_created', table_name='workspace_ownership_transfers')
    op.drop_index('ix_workspace_ownership_transfers_expires_pending', table_name='workspace_ownership_transfers')
    op.drop_index('ix_workspace_ownership_transfers_nominee_status', table_name='workspace_ownership_transfers')
    op.drop_index('uq_workspace_ownership_transfers_active_pending', table_name='workspace_ownership_transfers')
    op.drop_table('workspace_ownership_transfers')
