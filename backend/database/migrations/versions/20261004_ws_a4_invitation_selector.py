"""Add token_selector column and widen token_hash for workspace invitations.

Revision ID: ws_a4_invitation_selector
Revises: ws_a2_public_id
Create Date: 2026-10-04 12:05:00.000000+00:00

"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "ws_a4_invitation_selector"
down_revision: Union[str, None] = "ws_a2_public_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add token_selector column for O(1) indexed lookup of salted bcrypt invitation secrets
    op.add_column(
        "workspace_invitations",
        sa.Column("token_selector", sa.String(length=64), nullable=True),
    )

    # 2. Create unique index on token_selector
    op.create_index(
        "ix_workspace_invitations_token_selector",
        "workspace_invitations",
        ["token_selector"],
        unique=True,
    )

    # 3. Widen token_hash to VARCHAR(255) for salted KDF verifiers
    op.alter_column(
        "workspace_invitations",
        "token_hash",
        type_=sa.String(length=255),
        existing_type=sa.String(length=64),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "workspace_invitations",
        "token_hash",
        type_=sa.String(length=64),
        existing_type=sa.String(length=255),
        existing_nullable=False,
    )
    op.drop_index("ix_workspace_invitations_token_selector", table_name="workspace_invitations")
    op.drop_column("workspace_invitations", "token_selector")
