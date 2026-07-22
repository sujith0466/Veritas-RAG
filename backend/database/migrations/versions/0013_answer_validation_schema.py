"""answer_validation_schema

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-20 13:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "validation_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("overall_verdict", sa.String(length=32), nullable=False),
        sa.Column("entailment_ratio", sa.Float(), nullable=False),
        sa.Column("unsupported_claim_count", sa.Integer(), nullable=False),
        sa.Column("invalid_citation_count", sa.Integer(), nullable=False),
        sa.Column("is_valid", sa.Boolean(), nullable=False),
        sa.Column("metadata_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_validation_logs_correlation_id"),
        "validation_logs",
        ["correlation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_validation_logs_tenant_id"),
        "validation_logs",
        ["tenant_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_validation_logs_tenant_id"), table_name="validation_logs")
    op.drop_index(
        op.f("ix_validation_logs_correlation_id"), table_name="validation_logs"
    )
    op.drop_table("validation_logs")
