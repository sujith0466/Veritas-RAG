"""Section 6: Workspace Membership Modernization - VIEWER to MEMBER Migration

Revision ID: 20261115_sec6_viewer_mig
Revises: 20261115_sec4_5_mod
Create Date: 2026-11-15 00:00:00.000000+00:00

Governed by: Combined Implementation Plan Revision 4.14 (Section 6).
Binding Project Owner Policy:
1. Converts all existing workspace membership records with role = 'VIEWER' to 'MEMBER'
   across all statuses (ACTIVE, SUSPENDED, INACTIVE, and soft-deleted is_deleted=true/false).
2. Preserves all other membership data: status, IDs, timestamps, user/workspace
   associations, and member_metadata.
3. Does not modify global users.role = 'viewer'.
4. Tracks converted rows in a dedicated fail-closed tracking table:
   '_migration_sec6_viewer_conversions'
5. Fully reversible downgrade: restores original_role only for rows whose current
   role remains 'MEMBER', preserving subsequent promotions/changes.
"""

from collections.abc import Sequence
import logging
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

logger = logging.getLogger("alembic.runtime.migration")

# revision identifiers, used by Alembic.
revision: str = '20261115_sec6_viewer_mig'
down_revision: Union[str, None] = '20261115_sec4_5_mod'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Create dedicated tracking table (fail-closed, no IF NOT EXISTS)
    op.create_table(
        '_migration_sec6_viewer_conversions',
        sa.Column('member_id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('original_role', sa.String(length=50), nullable=False),
        sa.Column('converted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    # 2. Record all existing VIEWER memberships into tracking table (fail-closed, no ON CONFLICT DO NOTHING)
    conn.execute(sa.text("""
        INSERT INTO _migration_sec6_viewer_conversions (member_id, original_role)
        SELECT id, role
        FROM workspace_members
        WHERE UPPER(role) = 'VIEWER'
    """))

    # 3. Convert tracked workspace membership records to 'MEMBER'
    # Mutates ONLY 'role'; preserves status, is_deleted, member_metadata, timestamps, and version.
    conn.execute(sa.text("""
        UPDATE workspace_members
        SET role = 'MEMBER'
        WHERE id IN (SELECT member_id FROM _migration_sec6_viewer_conversions)
          AND UPPER(role) = 'VIEWER'
    """))


def downgrade() -> None:
    conn = op.get_bind()

    # 1. Revert converted records back to original_role ONLY if current role is still 'MEMBER'.
    # Preserves intervening administrative role changes (e.g. promotions to ADMIN).
    conn.execute(sa.text("""
        UPDATE workspace_members wm
        SET role = track.original_role
        FROM _migration_sec6_viewer_conversions track
        WHERE wm.id = track.member_id AND wm.role = 'MEMBER'
    """))

    # 2. Drop tracking table
    op.drop_table('_migration_sec6_viewer_conversions')
