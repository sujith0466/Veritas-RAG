"""llm audit telemetry

Revision ID: 0022
Revises: 0021
Create Date: 2026-07-27 09:20:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_audit_records",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("correlation_id", sa.String(length=100), nullable=True),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=True),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("prompt_hash", sa.String(length=64), nullable=False),
        sa.Column("prompt_text", sa.Text(), nullable=True),
        sa.Column("system_prompt_text", sa.Text(), nullable=True),
        sa.Column("prompt_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("response_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_response_text", sa.Text(), nullable=True),
        sa.Column("final_response_text", sa.Text(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "metadata_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_llm_audit_corr_idx", "llm_audit_records", ["correlation_id"])
    op.create_index("ix_llm_audit_created_idx", "llm_audit_records", ["created_at"])
    op.create_index(
        "ix_llm_audit_provider_model_idx",
        "llm_audit_records",
        ["provider", "model"],
    )


def downgrade() -> None:
    op.drop_index("ix_llm_audit_provider_model_idx", table_name="llm_audit_records")
    op.drop_index("ix_llm_audit_created_idx", table_name="llm_audit_records")
    op.drop_index("ix_llm_audit_corr_idx", table_name="llm_audit_records")
    op.drop_table("llm_audit_records")
