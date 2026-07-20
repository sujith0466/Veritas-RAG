"""Create vector storage schema: vector_index_metadata.

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-19 03:50:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vector_index_metadata",
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("collection_name", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column("points_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_version_id"], ["document_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "document_version_id", "collection_name", name="uq_vector_index_tenant_ver_col"),
    )
    op.create_index("ix_vector_metadata_tenant_status_idx", "vector_index_metadata", ["tenant_id", "status"])
    op.create_index("ix_vector_metadata_doc_ver_idx", "vector_index_metadata", ["document_id", "document_version_id"])
    op.create_index(op.f("ix_vector_index_metadata_tenant_id"), "vector_index_metadata", ["tenant_id"])
    op.create_index(op.f("ix_vector_index_metadata_document_id"), "vector_index_metadata", ["document_id"])
    op.create_index(op.f("ix_vector_index_metadata_document_version_id"), "vector_index_metadata", ["document_version_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_vector_index_metadata_document_version_id"), table_name="vector_index_metadata")
    op.drop_index(op.f("ix_vector_index_metadata_document_id"), table_name="vector_index_metadata")
    op.drop_index(op.f("ix_vector_index_metadata_tenant_id"), table_name="vector_index_metadata")
    op.drop_index("ix_vector_metadata_doc_ver_idx", table_name="vector_index_metadata")
    op.drop_index("ix_vector_metadata_tenant_status_idx", table_name="vector_index_metadata")
    op.drop_table("vector_index_metadata")
