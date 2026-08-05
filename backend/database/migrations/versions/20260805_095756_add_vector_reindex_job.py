"""Add VectorReindexJob model

Revision ID: 20260805_095756_add_vector_reindex_job
Revises: 61995c415127
Create Date: 2026-08-05T09:57:56.087719

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260805_095756_add_vector_reindex_job'
down_revision = '61995c415127'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'vector_reindex_jobs',
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('source_alias', sa.String(), nullable=False),
        sa.Column('staging_collection', sa.String(), nullable=False),
        sa.Column('previous_collection', sa.String(), nullable=True),
        sa.Column('target_model', sa.String(), nullable=False),
        sa.Column('total_documents', sa.Integer(), nullable=False),
        sa.Column('processed_documents', sa.Integer(), nullable=False),
        sa.Column('total_vectors_indexed', sa.Integer(), nullable=False),
        sa.Column('parity_verified', sa.Boolean(), nullable=False),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_vector_reindex_jobs'))
    )
    op.create_index(op.f('ix_vector_reindex_jobs_workspace_id'), 'vector_reindex_jobs', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_vector_reindex_jobs_id'), 'vector_reindex_jobs', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_vector_reindex_jobs_id'), table_name='vector_reindex_jobs')
    op.drop_index(op.f('ix_vector_reindex_jobs_workspace_id'), table_name='vector_reindex_jobs')
    op.drop_table('vector_reindex_jobs')
