"""Add source_type, source_url, canonical_url, final_url, and last_fetched_at to documents table.

Revision ID: d4_001_source_url
Revises: d2_001_job_dispatch
Create Date: 2026-10-02 10:00:00.000000+00:00

"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4_001_source_url"
down_revision: Union[str, None] = "d2_001_job_dispatch"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add columns to documents table
    op.add_column(
        "documents",
        sa.Column(
            "source_type",
            sa.String(length=50),
            server_default="file_upload",
            nullable=False,
        ),
    )
    op.add_column(
        "documents",
        sa.Column("source_url", sa.String(length=2048), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("canonical_url", sa.String(length=2048), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("final_url", sa.String(length=2048), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 2. Add index for source_type queries
    op.create_index(
        "ix_documents_source_type",
        "documents",
        ["source_type"],
        unique=False,
    )

    # 3. Backfill existing records safely to 'file_upload'
    op.execute(
        """
        UPDATE documents
        SET source_type = 'file_upload'
        WHERE source_type IS NULL;
        """
    )


def downgrade() -> None:
    op.drop_index("ix_documents_source_type", table_name="documents")
    op.drop_column("documents", "last_fetched_at")
    op.drop_column("documents", "final_url")
    op.drop_column("documents", "canonical_url")
    op.drop_column("documents", "source_url")
    op.drop_column("documents", "source_type")
