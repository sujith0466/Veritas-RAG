"""Add workspaces.public_id column, backfill existing records, and enforce unique not-null constraint.

Revision ID: ws_a2_public_id
Revises: ops_001_norm_score
Create Date: 2026-10-04 11:00:00.000000+00:00

"""

from collections.abc import Sequence
import re
import secrets
from typing import Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "ws_a2_public_id"
down_revision: Union[str, None] = "ops_001_norm_score"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CROCKFORD_ALPHABET = "23456789ABCDEFGHJKMNPQRSTVWXYZ"
WORKSPACE_ID_REGEX = r"^[A-Z0-9]{2,20}(?:-[A-Z0-9]{2,12})*$"


def upgrade() -> None:
    # 1. Add public_id as nullable column initially
    op.add_column(
        "workspaces",
        sa.Column("public_id", sa.String(length=50), nullable=True),
    )

    # 2. Backfill existing records with unique, canonical public IDs
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, name FROM workspaces")).fetchall()

    used_public_ids: set[str] = set()

    for row in rows:
        ws_id = row[0]
        ws_name = row[1]

        # Extract uppercase alphanumeric prefix from name, minimum 2 chars, max 10
        clean = re.sub(r"[^A-Za-z0-9]+", "", str(ws_name or "")).upper()
        prefix = clean[:10] if len(clean) >= 2 else "WS"

        # Generate unique candidate using Crockford Base32 entropy
        while True:
            suffix = "".join(secrets.choice(CROCKFORD_ALPHABET) for _ in range(6))
            candidate = f"{prefix}-{suffix}"
            if re.match(WORKSPACE_ID_REGEX, candidate) and candidate not in used_public_ids:
                used_public_ids.add(candidate)
                break

        bind.execute(
            sa.text("UPDATE workspaces SET public_id = :pub_id WHERE id = :ws_id"),
            {"pub_id": candidate, "ws_id": ws_id},
        )

    # 3. Create unique index
    op.create_index(
        "ix_workspaces_public_id",
        "workspaces",
        ["public_id"],
        unique=True,
    )

    # 4. Enforce NOT NULL constraint
    op.alter_column(
        "workspaces",
        "public_id",
        nullable=False,
    )


def downgrade() -> None:
    op.drop_index("ix_workspaces_public_id", table_name="workspaces")
    op.drop_column("workspaces", "public_id")
