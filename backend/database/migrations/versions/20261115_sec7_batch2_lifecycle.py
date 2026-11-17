"""Section 7: Batch 2 - Workspace Ownership Transfer Lifecycle & Safe Departure

Revision ID: 20261115_sec7_batch2_lifecycle
Revises: 20261115_sec7_batch1_transfer
Create Date: 2026-11-15 16:00:00.000000+00:00

Governed by: Combined Implementation Plan Revision 4.14 (Section 7, Batch 2 - V3.0)
Binding Project Owner Policy:
1. Adds former_owner_choice, decision_status, and canonical decision_deadline_at to workspace_ownership_transfers.
2. Adds is_former_owner boolean and chk_former_owner_never_viewer constraint to workspace_members.
3. Creates workspace_ownership_role_reminders table for tracking 14, 25, and 29-day reminders to new owner.
4. Fully reversible downgrade.
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20261115_sec7_batch2_lifecycle'
down_revision: Union[str, None] = '20261115_sec7_batch1_transfer'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Extend workspace_ownership_transfers
    op.add_column(
        'workspace_ownership_transfers',
        sa.Column('former_owner_choice', sa.String(length=20), server_default='PENDING', nullable=False)
    )
    op.add_column(
        'workspace_ownership_transfers',
        sa.Column('former_owner_choice_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        'workspace_ownership_transfers',
        sa.Column('decision_status', sa.String(length=30), server_default='PENDING', nullable=False)
    )
    op.add_column(
        'workspace_ownership_transfers',
        sa.Column('decision_deadline_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        'workspace_ownership_transfers',
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        'workspace_ownership_transfers',
        sa.Column('decided_by_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    )
    op.add_column(
        'workspace_ownership_transfers',
        sa.Column('response_notes', sa.Text(), nullable=True)
    )
    op.add_column(
        'workspace_ownership_transfers',
        sa.Column('decision_notes', sa.Text(), nullable=True)
    )

    op.create_check_constraint(
        'chk_former_owner_choice',
        'workspace_ownership_transfers',
        "former_owner_choice IN ('PENDING', 'STAY', 'LEAVE')"
    )
    op.create_check_constraint(
        'chk_decision_status',
        'workspace_ownership_transfers',
        "decision_status IN ('PENDING', 'DECIDED_ADMIN', 'DECIDED_MEMBER', 'DECIDED_REMOVED', 'FALLBACK_ADMIN', 'TIMED_OUT')"
    )

    # Backfill decision_deadline_at for existing rows
    op.execute(
        """
        UPDATE workspace_ownership_transfers
        SET decision_deadline_at = responded_at + INTERVAL '30 days'
        WHERE responded_at IS NOT NULL AND decision_deadline_at IS NULL
        """
    )
    op.execute(
        """
        UPDATE workspace_ownership_transfers
        SET decision_deadline_at = created_at + INTERVAL '30 days'
        WHERE decision_deadline_at IS NULL
        """
    )

    # 2. Extend workspace_members
    op.add_column(
        'workspace_members',
        sa.Column('is_former_owner', sa.Boolean(), server_default='false', nullable=False)
    )
    op.create_check_constraint(
        'chk_former_owner_never_viewer',
        'workspace_members',
        "NOT (is_former_owner = TRUE AND UPPER(role) = 'VIEWER')"
    )

    # 3. Create workspace_ownership_role_reminders
    op.create_table(
        'workspace_ownership_role_reminders',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('transfer_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspace_ownership_transfers.id', ondelete='CASCADE'), nullable=False),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('recipient_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('reminder_type', sa.String(length=20), nullable=False),
        sa.Column('scheduled_for', sa.DateTime(timezone=True), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='PENDING', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('clock_timestamp()'), nullable=False),
        sa.CheckConstraint("reminder_type IN ('DAY_14', 'DAY_25', 'DAY_29')", name='chk_reminder_type'),
        sa.CheckConstraint("status IN ('PENDING', 'SENT', 'CANCELLED', 'SKIPPED')", name='chk_reminder_status'),
        sa.UniqueConstraint('transfer_id', 'reminder_type', name='uq_transfer_reminder_type'),
    )

    op.create_index(
        'ix_role_reminders_pending_scheduled',
        'workspace_ownership_role_reminders',
        ['status', 'scheduled_for'],
        postgresql_where=sa.text("status = 'PENDING'")
    )
    op.create_index(
        'ix_role_reminders_transfer_id',
        'workspace_ownership_role_reminders',
        ['transfer_id']
    )


def downgrade() -> None:
    op.drop_index('ix_role_reminders_transfer_id', table_name='workspace_ownership_role_reminders')
    op.drop_index('ix_role_reminders_pending_scheduled', table_name='workspace_ownership_role_reminders')
    op.drop_table('workspace_ownership_role_reminders')

    op.drop_constraint('chk_former_owner_never_viewer', 'workspace_members', type_='check')
    op.drop_column('workspace_members', 'is_former_owner')

    op.drop_constraint('chk_decision_status', 'workspace_ownership_transfers', type_='check')
    op.drop_constraint('chk_former_owner_choice', 'workspace_ownership_transfers', type_='check')

    op.drop_column('workspace_ownership_transfers', 'decision_notes')
    op.drop_column('workspace_ownership_transfers', 'response_notes')
    op.drop_column('workspace_ownership_transfers', 'decided_by_user_id')
    op.drop_column('workspace_ownership_transfers', 'decided_at')
    op.drop_column('workspace_ownership_transfers', 'decision_deadline_at')
    op.drop_column('workspace_ownership_transfers', 'decision_status')
    op.drop_column('workspace_ownership_transfers', 'former_owner_choice_at')
    op.drop_column('workspace_ownership_transfers', 'former_owner_choice')
