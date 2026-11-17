"""section_4_5_modernization

Revision ID: 20261115_sec4_5_mod
Revises: 20261112_uq_ws_active_owner
Create Date: 2026-11-15 00:00:00.000000+00:00

Governed by: Master Plan Version 2.6 (Combined Sections 4 & 5).
Implements:
1. Creator-scoped join codes (workspace_join_codes) with AES-256-GCM and dual-pepper HMAC lookup.
2. Reusable invitation links with optional email and legacy-bound preservation.
3. Immutable redemption ledgers (workspace_join_code_redemptions, workspace_invitation_redemptions) with ON DELETE RESTRICT.
4. Transactional notification outbox (notification_outbox) with lease-based claiming.
5. Non-destructive downgrade protocol preserving audit history via archived_* tables.
"""

from collections.abc import Sequence
import logging
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

logger = logging.getLogger("alembic.runtime.migration")

# revision identifiers, used by Alembic.
revision: str = '20261115_sec4_5_mod'
down_revision: Union[str, None] = '20261112_uq_ws_active_owner'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Update workspace_invitations table: email nullable, is_legacy_bound flag
    op.alter_column(
        'workspace_invitations',
        'email',
        existing_type=sa.String(length=255),
        nullable=True,
    )
    op.add_column(
        'workspace_invitations',
        sa.Column('is_legacy_bound', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )

    # Mark pre-existing invitations as legacy-bound to preserve email locking
    conn.execute(
        sa.text("UPDATE workspace_invitations SET is_legacy_bound = true WHERE email IS NOT NULL AND status = 'PENDING'")
    )

    # 2. Create workspace_join_codes table
    op.create_table(
        'workspace_join_codes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('created_by_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('operational_custodian_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('code_hash', sa.String(length=64), nullable=False, unique=True),
        sa.Column('lookup_pepper_version', sa.String(length=16), nullable=False, server_default='v1'),
        sa.Column('encrypted_code', sa.Text(), nullable=False),
        sa.Column('encryption_key_version', sa.String(length=16), nullable=False, server_default='enc_v1'),
        sa.Column('code_display', sa.String(length=32), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('is_legacy', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('use_count', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('version', sa.Integer(), nullable=False, server_default=sa.text('1')),
        sa.Column('warning_3d_sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('warning_24h_sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('warning_1h_sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('warning_expired_sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('clock_timestamp()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('clock_timestamp()')),
    )
    op.create_index('idx_wjc_workspace_creator', 'workspace_join_codes', ['workspace_id', 'created_by_user_id'])
    op.create_index('idx_wjc_active_lookup', 'workspace_join_codes', ['workspace_id', 'is_enabled', 'expires_at'])
    op.create_index(
        'uq_wjc_active_creator',
        'workspace_join_codes',
        ['workspace_id', 'created_by_user_id'],
        unique=True,
        postgresql_where=sa.text('is_enabled = true'),
    )

    # 3. Create workspace_join_code_redemptions table (Audit Protected)
    op.create_table(
        'workspace_join_code_redemptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('join_code_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspace_join_codes.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('redeemed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('clock_timestamp()')),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('clock_timestamp()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('clock_timestamp()')),
        sa.UniqueConstraint('join_code_id', 'user_id', name='uq_wjc_redemption'),
    )
    op.create_index('idx_wjcr_workspace', 'workspace_join_code_redemptions', ['workspace_id'])
    op.create_index('idx_wjcr_user', 'workspace_join_code_redemptions', ['user_id'])

    # 4. Create workspace_invitation_redemptions table (Audit Protected)
    op.create_table(
        'workspace_invitation_redemptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('invitation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspace_invitations.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('redeemed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('clock_timestamp()')),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('clock_timestamp()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('clock_timestamp()')),
        sa.UniqueConstraint('invitation_id', 'user_id', name='uq_wir_redemption'),
    )
    op.create_index('idx_wir_invitation', 'workspace_invitation_redemptions', ['invitation_id'])
    op.create_index('idx_wir_user', 'workspace_invitation_redemptions', ['user_id'])

    # 5. Create notification_outbox table
    op.create_table(
        'notification_outbox',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('join_code_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspace_join_codes.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('join_code_version', sa.Integer(), nullable=False, server_default=sa.text('1')),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('recipient_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('checkpoint', sa.String(length=32), nullable=False),
        sa.Column('channel', sa.String(length=32), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='PENDING'),
        sa.Column('idempotency_key', sa.String(length=64), nullable=False, unique=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('lease_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('scheduled_for', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('clock_timestamp()')),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('clock_timestamp()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('clock_timestamp()')),
    )
    op.create_index(
        'idx_notif_outbox_claim',
        'notification_outbox',
        ['status', 'scheduled_for', 'lease_expires_at'],
        postgresql_where=sa.text("status IN ('PENDING', 'CLAIMED')"),
    )


def downgrade() -> None:
    """Non-destructive constraint-safe downgrade preserving historical audit ledgers."""
    conn = op.get_bind()

    # Dynamic SQL execution to rename tables to archived_* and reconcile FK constraints
    downgrade_sql = """
    DO $$
    DECLARE
        r RECORD;
    BEGIN
        -- 1. Rename active tables to archival tables to preserve historical evidence
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'workspace_join_codes') THEN
            ALTER TABLE workspace_join_codes RENAME TO archived_workspace_join_codes;
        END IF;

        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'workspace_join_code_redemptions') THEN
            ALTER TABLE workspace_join_code_redemptions RENAME TO archived_workspace_join_code_redemptions;
        END IF;

        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'workspace_invitation_redemptions') THEN
            ALTER TABLE workspace_invitation_redemptions RENAME TO archived_workspace_invitation_redemptions;
        END IF;

        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'notification_outbox') THEN
            ALTER TABLE notification_outbox RENAME TO archived_notification_outbox;
        END IF;

        -- 2. Drop NOT NULL requirements on referencing columns before converting to SET NULL
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'archived_workspace_join_code_redemptions') THEN
            ALTER TABLE archived_workspace_join_code_redemptions ALTER COLUMN join_code_id DROP NOT NULL;
            ALTER TABLE archived_workspace_join_code_redemptions ALTER COLUMN workspace_id DROP NOT NULL;
            ALTER TABLE archived_workspace_join_code_redemptions ALTER COLUMN user_id DROP NOT NULL;
        END IF;

        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'archived_workspace_invitation_redemptions') THEN
            ALTER TABLE archived_workspace_invitation_redemptions ALTER COLUMN invitation_id DROP NOT NULL;
            ALTER TABLE archived_workspace_invitation_redemptions ALTER COLUMN workspace_id DROP NOT NULL;
            ALTER TABLE archived_workspace_invitation_redemptions ALTER COLUMN user_id DROP NOT NULL;
        END IF;

        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'archived_notification_outbox') THEN
            ALTER TABLE archived_notification_outbox ALTER COLUMN join_code_id DROP NOT NULL;
            ALTER TABLE archived_notification_outbox ALTER COLUMN workspace_id DROP NOT NULL;
            ALTER TABLE archived_notification_outbox ALTER COLUMN recipient_user_id DROP NOT NULL;
        END IF;

        -- 3. Discover and drop all existing RESTRICT foreign key constraints on archived tables
        FOR r IN (
            SELECT conname, conrelid::regclass::text as tablename
            FROM pg_constraint
            WHERE conrelid IN (
                'archived_workspace_join_codes'::regclass,
                'archived_workspace_join_code_redemptions'::regclass,
                'archived_workspace_invitation_redemptions'::regclass,
                'archived_notification_outbox'::regclass
            ) AND contype = 'f'
        ) LOOP
            EXECUTE 'ALTER TABLE ' || quote_ident(r.tablename) || ' DROP CONSTRAINT ' || quote_ident(r.conname);
        END LOOP;

        -- 4. Re-link foreign keys to active tables with ON DELETE SET NULL
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'archived_workspace_join_code_redemptions') THEN
            ALTER TABLE archived_workspace_join_code_redemptions 
                ADD CONSTRAINT fk_archived_wjcr_code FOREIGN KEY (join_code_id) REFERENCES archived_workspace_join_codes(id) ON DELETE SET NULL,
                ADD CONSTRAINT fk_archived_wjcr_ws FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE SET NULL,
                ADD CONSTRAINT fk_archived_wjcr_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL;
        END IF;

        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'archived_workspace_invitation_redemptions') THEN
            ALTER TABLE archived_workspace_invitation_redemptions 
                ADD CONSTRAINT fk_archived_wir_invite FOREIGN KEY (invitation_id) REFERENCES workspace_invitations(id) ON DELETE SET NULL,
                ADD CONSTRAINT fk_archived_wir_ws FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE SET NULL,
                ADD CONSTRAINT fk_archived_wir_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL;
        END IF;
    END $$;
    """
    conn.execute(sa.text(downgrade_sql))

    # Revert workspace_invitations changes safely
    if op.get_bind().dialect.name == "postgresql":
        conn.execute(sa.text("ALTER TABLE workspace_invitations DROP COLUMN IF EXISTS is_legacy_bound"))
