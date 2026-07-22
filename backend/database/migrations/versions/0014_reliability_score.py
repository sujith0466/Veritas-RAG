"""reliability_score

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-20 14:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scoring_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("final_score", sa.Float(), nullable=False),
        sa.Column("is_trusted", sa.Boolean(), nullable=False),
        sa.Column("metadata_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_scoring_logs_correlation_id"),
        "scoring_logs",
        ["correlation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_scoring_logs_tenant_id"), "scoring_logs", ["tenant_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_scoring_logs_tenant_id"), table_name="scoring_logs")
    op.drop_index(op.f("ix_scoring_logs_correlation_id"), table_name="scoring_logs")
    op.drop_table("scoring_logs")
