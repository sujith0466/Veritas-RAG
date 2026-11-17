"""Unit tests for Package T-3.C Work Package WP-T3C-1.

Verifies:
1. Core invariant declarations on WorkspaceMember SQLAlchemy entity.
2. Model index parity with Alembic migration 20261112_uq_ws_active_owner.py.
3. Pydantic schema validation for canonical workspace roles.
"""

import uuid
import pytest
from pydantic import ValidationError

from backend.api.v1.schemas.workspace_member import (
    ASSIGNABLE_WORKSPACE_ROLES,
    BulkMemberActionRequest,
    UpdateMemberRoleRequest,
)
from backend.models.entities.workspace_member import WorkspaceMember, WorkspaceRole


class TestWorkspaceMemberModelParity:
    """Tests model-level table args and index declarations for WorkspaceMember."""

    def test_workspace_member_declared_indexes(self):
        """Verify that WorkspaceMember declares both active user and active owner unique indexes."""
        table = WorkspaceMember.__table__
        index_names = {idx.name for idx in table.indexes}

        assert "uq_workspace_members_active_user" in index_names, (
            "Missing uq_workspace_members_active_user index in WorkspaceMember.__table_args__"
        )
        assert "uq_workspace_members_active_owner" in index_names, (
            "Missing uq_workspace_members_active_owner index in WorkspaceMember.__table_args__"
        )

    def test_active_owner_index_properties(self):
        """Verify that uq_workspace_members_active_owner matches the accepted Alembic migration."""
        table = WorkspaceMember.__table__
        owner_idx = next(idx for idx in table.indexes if idx.name == "uq_workspace_members_active_owner")

        # 1. Column specification: exactly ['workspace_id']
        col_names = [col.name for col in owner_idx.columns]
        assert col_names == ["workspace_id"], (
            f"Expected indexed column ['workspace_id'], got {col_names}"
        )

        # 2. Unique constraint
        assert owner_idx.unique is True, "Index uq_workspace_members_active_owner must be unique"

        # 3. Dialect-specific partial index predicate
        dialect_options = owner_idx.dialect_options.get("postgresql", {})
        pg_where = str(dialect_options.get("where", ""))
        assert "role = 'OWNER'" in pg_where, f"Predicate missing role = 'OWNER': {pg_where}"
        assert "is_deleted = false" in pg_where, f"Predicate missing is_deleted = false: {pg_where}"

    def test_active_user_index_properties(self):
        """Verify that uq_workspace_members_active_user remains intact."""
        table = WorkspaceMember.__table__
        user_idx = next(idx for idx in table.indexes if idx.name == "uq_workspace_members_active_user")

        col_names = [col.name for col in user_idx.columns]
        assert col_names == ["workspace_id", "user_id"], (
            f"Expected indexed columns ['workspace_id', 'user_id'], got {col_names}"
        )
        assert user_idx.unique is True
        dialect_options = user_idx.dialect_options.get("postgresql", {})
        pg_where = str(dialect_options.get("where", ""))
        assert "is_deleted = false" in pg_where


class TestWorkspaceMemberSchemaValidation:
    """Tests Pydantic schema validation for canonical roles and rejection of unassignable roles."""

    def test_assignable_roles_set(self):
        """Verify assignable workspace roles set contains strictly ADMIN and MEMBER."""
        assert ASSIGNABLE_WORKSPACE_ROLES == {"ADMIN", "MEMBER"}

    def test_update_member_role_request_accepts_assignable_roles(self):
        """Verify UpdateMemberRoleRequest accepts ADMIN and MEMBER."""
        req_admin = UpdateMemberRoleRequest(role="ADMIN")
        assert req_admin.role == "ADMIN"
        req_member = UpdateMemberRoleRequest(role="MEMBER")
        assert req_member.role == "MEMBER"

    def test_update_member_role_request_rejects_owner(self):
        """Verify direct promotion or assignment to OWNER is rejected with clear error."""
        with pytest.raises(ValidationError, match="Direct assignment or promotion to OWNER is not permitted"):
            UpdateMemberRoleRequest(role="OWNER")

    def test_update_member_role_request_rejects_viewer(self):
        """Verify assignment of deprecated VIEWER role is rejected."""
        with pytest.raises(ValidationError, match="Role VIEWER is deprecated and cannot be assigned"):
            UpdateMemberRoleRequest(role="VIEWER")

    def test_update_member_role_request_rejects_noncanonical_formatting(self):
        """Verify lowercase and whitespace formatting is rejected without silent normalization."""
        for noncanonical in ["admin", "member", " ADMIN ", " Member "]:
            with pytest.raises(ValidationError, match="Noncanonical role value"):
                UpdateMemberRoleRequest(role=noncanonical)

    def test_bulk_member_action_request_role_validation(self):
        """Verify BulkMemberActionRequest rejects OWNER and VIEWER for update_role."""
        m_id = uuid.uuid4()
        with pytest.raises(ValidationError, match="Direct assignment or promotion to OWNER is not permitted in bulk operations"):
            BulkMemberActionRequest(action="update_role", member_ids=[m_id], role="OWNER")

        with pytest.raises(ValidationError, match="Role VIEWER is deprecated and cannot be assigned in bulk operations"):
            BulkMemberActionRequest(action="update_role", member_ids=[m_id], role="VIEWER")
