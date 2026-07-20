"""Create chunking foundation schema: document_chunks, chunk_relationships.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-19 02:00:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create document_chunks table
    op.create_table(
        "document_chunks",
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("strategy_used", sa.String(length=50), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("character_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("parent_chunk_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("previous_chunk_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("next_chunk_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("page_numbers", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("section_path", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_embedded", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_version_id"], ["document_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_chunk_id"], ["document_chunks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["previous_chunk_id"], ["document_chunks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["next_chunk_id"], ["document_chunks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_document_chunks_tenant_id"), "document_chunks", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_document_chunks_document_id"), "document_chunks", ["document_id"], unique=False)
    op.create_index(op.f("ix_document_chunks_document_version_id"), "document_chunks", ["document_version_id"], unique=False)
    op.create_index(op.f("ix_document_chunks_content_hash"), "document_chunks", ["content_hash"], unique=False)
    op.create_index(op.f("ix_document_chunks_parent_chunk_id"), "document_chunks", ["parent_chunk_id"], unique=False)
    op.create_index(
        "ix_document_chunks_tenant_doc_ver_idx",
        "document_chunks",
        ["tenant_id", "document_id", "document_version_id", "chunk_index"],
        unique=False,
    )
    op.create_index(
        "ix_document_chunks_tenant_hash",
        "document_chunks",
        ["tenant_id", "content_hash"],
        unique=False,
    )

    # 2. Create chunk_relationships table
    op.create_table(
        "chunk_relationships",
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("source_chunk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_chunk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("relationship_type", sa.String(length=50), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.ForeignKeyConstraint(["source_chunk_id"], ["document_chunks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_chunk_id"], ["document_chunks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_chunk_relationships_tenant_id"), "chunk_relationships", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_chunk_relationships_source_chunk_id"), "chunk_relationships", ["source_chunk_id"], unique=False)
    op.create_index(op.f("ix_chunk_relationships_target_chunk_id"), "chunk_relationships", ["target_chunk_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_chunk_relationships_target_chunk_id"), table_name="chunk_relationships")
    op.drop_index(op.f("ix_chunk_relationships_source_chunk_id"), table_name="chunk_relationships")
    op.drop_index(op.f("ix_chunk_relationships_tenant_id"), table_name="chunk_relationships")
    op.drop_table("chunk_relationships")

    op.drop_index("ix_document_chunks_tenant_hash", table_name="document_chunks")
    op.drop_index("ix_document_chunks_tenant_doc_ver_idx", table_name="document_chunks")
    op.drop_index(op.f("ix_document_chunks_parent_chunk_id"), table_name="document_chunks")
    op.drop_index(op.f("ix_document_chunks_content_hash"), table_name="document_chunks")
    op.drop_index(op.f("ix_document_chunks_document_version_id"), table_name="document_chunks")
    op.drop_index(op.f("ix_document_chunks_document_id"), table_name="document_chunks")
    op.drop_index(op.f("ix_document_chunks_tenant_id"), table_name="document_chunks")
    op.drop_table("document_chunks")
