"""Create knowledge health schema: health_scan_jobs and stale_embedding_records.

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-19 16:30:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. health_scan_jobs table
    op.create_table(
        "health_scan_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=100), nullable=False),
        sa.Column("scan_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column("orphans_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("orphans_purged", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stale_chunks_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("parity_status", sa.String(length=100), nullable=False, server_default="UNKNOWN"),
        sa.Column("duration_ms", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_health_scan_jobs")),
    )
    op.create_index(op.f("ix_health_scan_jobs_tenant_id"), "health_scan_jobs", ["tenant_id"], unique=False)
    op.create_index(
        "ix_health_scan_jobs_tenant_status",
        "health_scan_jobs",
        ["tenant_id", "scan_type", "status"],
        unique=False,
    )

    # 2. stale_embedding_records table
    op.create_table(
        "stale_embedding_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=100), nullable=False),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("old_provider", sa.String(length=50), nullable=False),
        sa.Column("old_model_name", sa.String(length=100), nullable=False),
        sa.Column("target_provider", sa.String(length=50), nullable=False),
        sa.Column("target_model_name", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["chunk_id"],
            ["document_chunks.id"],
            name=op.f("fk_stale_embedding_records_chunk_id_document_chunks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stale_embedding_records")),
    )
    op.create_index(op.f("ix_stale_embedding_records_tenant_id"), "stale_embedding_records", ["tenant_id"], unique=False)
    op.create_index(
        "ix_stale_embedding_records_tenant_chunk",
        "stale_embedding_records",
        ["tenant_id", "chunk_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("stale_embedding_records")
    op.drop_table("health_scan_jobs")
