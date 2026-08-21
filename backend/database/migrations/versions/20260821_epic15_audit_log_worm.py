"""Audit Log WORM immutability schema migration.

Removes `is_deleted` and `updated_at` columns from `audit_logs` table
to guarantee append-only Write-Once-Read-Many (WORM) storage integrity.

Revision ID: e15a0d179001
Revises: f1302e18ea08
Create Date: 2026-08-21 07:30:00.000000+00:00

"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e15a0d179001"
down_revision: Union[str, None] = "f1302e18ea08"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop mutable and soft-delete columns from audit_logs table
    op.drop_column("audit_logs", "is_deleted")
    op.drop_column("audit_logs", "updated_at")


def downgrade() -> None:
    # Restore columns with safe defaults in case of rollback
    op.add_column(
        "audit_logs",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.add_column(
        "audit_logs",
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
