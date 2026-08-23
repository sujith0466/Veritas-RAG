"""Add AI policies and policy violation audits tables.

Revision ID: e15_iss004_policies
Revises: e15a0d179001
Create Date: 2026-08-23 08:58:00.000000+00:00

"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "e15_iss004_policies"
down_revision: Union[str, None] = "e15a0d179001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create policies table
    op.create_table(
        "policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("workspace_id", sa.String(length=255), nullable=True),
        sa.Column("max_tokens", sa.Integer(), nullable=True),
        sa.Column("blocked_topics", sa.JSON(), nullable=True),
        sa.Column("redact_pii", sa.Boolean(), nullable=True),
        sa.Column("block_jailbreaks", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_index(op.f("ix_policies_tenant_id"), "policies", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_policies_workspace_id"), "policies", ["workspace_id"], unique=False)

    # Partial unique indexes for tenant-global and workspace-override scopes
    op.create_index(
        "uq_policies_tenant_global",
        "policies",
        ["tenant_id"],
        unique=True,
        postgresql_where=sa.text("workspace_id IS NULL"),
    )
    op.create_index(
        "uq_policies_tenant_workspace",
        "policies",
        ["tenant_id", "workspace_id"],
        unique=True,
        postgresql_where=sa.text("workspace_id IS NOT NULL"),
    )

    # 2. Create policy_violation_audits table
    op.create_table(
        "policy_violation_audits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("workspace_id", sa.String(length=255), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("violation_type", sa.String(length=100), nullable=False),
        sa.Column("action_taken", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index(op.f("ix_policy_violation_audits_tenant_id"), "policy_violation_audits", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_policy_violation_audits_workspace_id"), "policy_violation_audits", ["workspace_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_policy_violation_audits_workspace_id"), table_name="policy_violation_audits")
    op.drop_index(op.f("ix_policy_violation_audits_tenant_id"), table_name="policy_violation_audits")
    op.drop_table("policy_violation_audits")

    op.drop_index("uq_policies_tenant_workspace", table_name="policies")
    op.drop_index("uq_policies_tenant_global", table_name="policies")
    op.drop_index(op.f("ix_policies_workspace_id"), table_name="policies")
    op.drop_index(op.f("ix_policies_tenant_id"), table_name="policies")
    op.drop_table("policies")
