"""Create retrieval reliability schema: retrieval_sla_logs and circuit_breaker_events.

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-19 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. retrieval_sla_logs table
    op.create_table(
        "retrieval_sla_logs",
        sa.Column("tenant_id", sa.String(length=100), nullable=False),
        sa.Column("correlation_id", sa.String(length=100), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("target_module", sa.String(length=100), nullable=False, server_default="qdrant_hybrid"),
        sa.Column("duration_ms", sa.Float(), nullable=False),
        sa.Column("is_sla_breached", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_degraded_fallback", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("fallback_reason", sa.String(length=255), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sla_logs_tenant_created", "retrieval_sla_logs", ["tenant_id", "created_at"])
    op.create_index("ix_sla_logs_tenant_breach", "retrieval_sla_logs", ["tenant_id", "is_sla_breached"])
    op.create_index("ix_sla_logs_tenant_degraded", "retrieval_sla_logs", ["tenant_id", "is_degraded_fallback"])
    op.create_index(op.f("ix_retrieval_sla_logs_tenant_id"), "retrieval_sla_logs", ["tenant_id"])
    op.create_index(op.f("ix_retrieval_sla_logs_correlation_id"), "retrieval_sla_logs", ["correlation_id"])

    # 2. circuit_breaker_events table
    op.create_table(
        "circuit_breaker_events",
        sa.Column("tenant_id", sa.String(length=100), nullable=False),
        sa.Column("target_module", sa.String(length=100), nullable=False),
        sa.Column("previous_state", sa.String(length=50), nullable=False),
        sa.Column("new_state", sa.String(length=50), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("error_code", sa.String(length=50), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_circuit_events_tenant_target", "circuit_breaker_events", ["tenant_id", "target_module", "created_at"])
    op.create_index(op.f("ix_circuit_breaker_events_tenant_id"), "circuit_breaker_events", ["tenant_id"])
    op.create_index(op.f("ix_circuit_breaker_events_target_module"), "circuit_breaker_events", ["target_module"])


def downgrade() -> None:
    op.drop_index(op.f("ix_circuit_breaker_events_target_module"), table_name="circuit_breaker_events")
    op.drop_index(op.f("ix_circuit_breaker_events_tenant_id"), table_name="circuit_breaker_events")
    op.drop_index("ix_circuit_events_tenant_target", table_name="circuit_breaker_events")
    op.drop_table("circuit_breaker_events")

    op.drop_index(op.f("ix_retrieval_sla_logs_correlation_id"), table_name="retrieval_sla_logs")
    op.drop_index(op.f("ix_retrieval_sla_logs_tenant_id"), table_name="retrieval_sla_logs")
    op.drop_index("ix_sla_logs_tenant_degraded", table_name="retrieval_sla_logs")
    op.drop_index("ix_sla_logs_tenant_breach", table_name="retrieval_sla_logs")
    op.drop_index("ix_sla_logs_tenant_created", table_name="retrieval_sla_logs")
    op.drop_table("retrieval_sla_logs")
