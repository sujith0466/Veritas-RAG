"""Create embedding pipeline schema: embedding_jobs, chunk_embeddings.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-19 03:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create embedding_jobs table
    op.create_table(
        "embedding_jobs",
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="PENDING"
        ),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("total_chunks", sa.Integer(), nullable=False),
        sa.Column("processed_chunks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_chunks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "total_tokens_consumed", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["document_version_id"], ["document_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_embedding_jobs_tenant_id"),
        "embedding_jobs",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_embedding_jobs_document_id"),
        "embedding_jobs",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        "ix_embedding_jobs_tenant_doc_ver_idx",
        "embedding_jobs",
        ["tenant_id", "document_version_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_embedding_jobs_tenant_created_idx",
        "embedding_jobs",
        ["tenant_id", "created_at"],
        unique=False,
    )

    # 2. Create chunk_embeddings table
    op.create_table(
        "chunk_embeddings",
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("dimension", sa.Integer(), nullable=False),
        sa.Column(
            "embedding_vector", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id"], ["document_chunks.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "chunk_id", name="uq_chunk_embeddings_tenant_chunk"
        ),
    )
    op.create_index(
        op.f("ix_chunk_embeddings_tenant_id"),
        "chunk_embeddings",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_chunk_embeddings_chunk_id"),
        "chunk_embeddings",
        ["chunk_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_chunk_embeddings_content_hash"),
        "chunk_embeddings",
        ["content_hash"],
        unique=False,
    )
    op.create_index(
        "ix_chunk_embeddings_tenant_hash_model_idx",
        "chunk_embeddings",
        ["tenant_id", "content_hash", "provider", "model_name"],
        unique=False,
    )
    op.create_index(
        "ix_chunk_embeddings_tenant_doc_ver_idx",
        "chunk_embeddings",
        ["tenant_id", "document_version_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_chunk_embeddings_tenant_doc_ver_idx", table_name="chunk_embeddings"
    )
    op.drop_index(
        "ix_chunk_embeddings_tenant_hash_model_idx", table_name="chunk_embeddings"
    )
    op.drop_index(
        op.f("ix_chunk_embeddings_content_hash"), table_name="chunk_embeddings"
    )
    op.drop_index(op.f("ix_chunk_embeddings_chunk_id"), table_name="chunk_embeddings")
    op.drop_index(op.f("ix_chunk_embeddings_tenant_id"), table_name="chunk_embeddings")
    op.drop_table("chunk_embeddings")

    op.drop_index("ix_embedding_jobs_tenant_created_idx", table_name="embedding_jobs")
    op.drop_index("ix_embedding_jobs_tenant_doc_ver_idx", table_name="embedding_jobs")
    op.drop_index(op.f("ix_embedding_jobs_document_id"), table_name="embedding_jobs")
    op.drop_index(op.f("ix_embedding_jobs_tenant_id"), table_name="embedding_jobs")
    op.drop_table("embedding_jobs")
