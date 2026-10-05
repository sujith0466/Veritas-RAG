"""Unit tests for WS-B1: Canonical Role & Membership Authority."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from pydantic import ValidationError

from backend.api.v1.schemas.workspace_member import UpdateMemberRoleRequest
from backend.core.permissions.guards import evaluate_role_access
from backend.core.permissions.rbac import Role, WORKSPACE_ROLES
from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember, WorkspaceRole
from backend.services.workspace.membership_service import (
    MembershipConflictError,
    MembershipError,
    MembershipUnauthorizedError,
    WorkspaceMembershipService,
)


def test_workspace_role_enum_canonical_values():
    """Verify that WorkspaceRole contains ONLY canonical uppercase roles."""
    expected = {"OWNER", "ADMIN", "MEMBER", "VIEWER"}
    actual = {r.value for r in WorkspaceRole}
    assert actual == expected, f"WorkspaceRole enum must only contain {expected}, got {actual}"


def test_workspace_role_bidirectional_conversion():
    """Verify lossless conversion between WorkspaceRole and RBAC Role."""
    for ws_role in WorkspaceRole:
        rbac_role = ws_role.to_rbac_role()
        assert isinstance(rbac_role, Role)
        assert rbac_role.value == ws_role.value.lower()
        # Convert back
        recovered_ws_role = rbac_role.to_workspace_role()
        assert recovered_ws_role == ws_role

    assert WorkspaceRole.from_rbac_role(Role.OWNER) == WorkspaceRole.OWNER
    assert WorkspaceRole.from_rbac_role(Role.ADMIN) == WorkspaceRole.ADMIN
    assert WorkspaceRole.from_rbac_role(Role.MEMBER) == WorkspaceRole.MEMBER
    assert WorkspaceRole.from_rbac_role(Role.VIEWER) == WorkspaceRole.VIEWER


def test_rbac_role_workspace_checks():
    """Verify Role.is_workspace_role and rejection of platform/specialized roles."""
    # Canonical workspace roles
    for r in WORKSPACE_ROLES:
        assert Role.is_workspace_role(r) is True
        assert Role.is_workspace_role(r.value) is True
        assert Role.is_workspace_role(r.value.upper()) is True

    # Platform roles must NOT be workspace roles
    assert Role.is_workspace_role(Role.PLATFORM_ADMIN) is False
    assert Role.is_workspace_role(Role.PLATFORM_SUPPORT) is False
    assert Role.is_workspace_role(Role.PLATFORM_AUDITOR) is False

    # Specialized roles (ENGINEER/ANALYST) must NOT be workspace membership roles
    assert Role.is_workspace_role(Role.ENGINEER) is False
    assert Role.is_workspace_role(Role.ANALYST) is False

    # Attempting to convert non-workspace role to WorkspaceRole must raise ValueError
    with pytest.raises(ValueError, match="not a valid workspace membership role"):
        Role.PLATFORM_ADMIN.to_workspace_role()

    with pytest.raises(ValueError, match="not a valid workspace membership role"):
        Role.ENGINEER.to_workspace_role()


def test_workspace_role_is_valid():
    """Verify WorkspaceRole.is_valid validates strings strictly."""
    assert WorkspaceRole.is_valid("OWNER") is True
    assert WorkspaceRole.is_valid("admin") is True  # Case insensitive
    assert WorkspaceRole.is_valid("Member") is True
    assert WorkspaceRole.is_valid("VIEWER") is True

    # Invalid strings must be rejected
    assert WorkspaceRole.is_valid("ENGINEER") is False
    assert WorkspaceRole.is_valid("ANALYST") is False
    assert WorkspaceRole.is_valid("PLATFORM_ADMIN") is False
    assert WorkspaceRole.is_valid("ROOT") is False
    assert WorkspaceRole.is_valid("") is False
    assert WorkspaceRole.is_valid(None) is False


def test_schema_rejects_non_canonical_workspace_roles():
    """Verify that UpdateMemberRoleRequest rejects non-canonical roles."""
    # Valid roles
    assert UpdateMemberRoleRequest(role="OWNER").role == "OWNER"
    assert UpdateMemberRoleRequest(role="admin").role == "ADMIN"
    assert UpdateMemberRoleRequest(role="MEMBER").role == "MEMBER"
    assert UpdateMemberRoleRequest(role="viewer").role == "VIEWER"

    # Non-canonical roles must be rejected
    invalid_roles = ["ENGINEER", "ANALYST", "PLATFORM_ADMIN", "superuser", "guest", "random"]
    for inv in invalid_roles:
        with pytest.raises(ValidationError):
            UpdateMemberRoleRequest(role=inv)


@pytest.mark.asyncio
async def test_self_role_modification_prevention():
    """Verify actor cannot modify their own role (self-escalation/demotion)."""
    ws_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    member_id = uuid.uuid4()

    member_repo = MagicMock()
    workspace_repo = MagicMock()
    service = WorkspaceMembershipService(member_repo=member_repo, workspace_repo=workspace_repo)

    workspace = Workspace(id=ws_id, name="Test WS", slug="test-ws", status=WorkspaceStatus.ACTIVE.value)
    workspace_repo.get_by_id = AsyncMock(return_value=workspace)

    # Actor has ID actor_id, target member ALSO has ID actor_id
    actor_member = WorkspaceMember(
        id=member_id,
        workspace_id=ws_id,
        user_id=actor_id,
        role=WorkspaceRole.ADMIN.value,
        status=MemberStatus.ACTIVE.value,
    )
    member_repo.get_membership = AsyncMock(return_value=actor_member)
    member_repo.get_by_id_for_update = AsyncMock(return_value=actor_member)

    session = AsyncMock()

    with pytest.raises(MembershipUnauthorizedError, match="You cannot modify your own role"):
        await service.update_member_role(
            session=session,
            workspace_id=ws_id,
            actor_id=actor_id,
            member_id=member_id,
            new_role="MEMBER",
        )


@pytest.mark.asyncio
async def test_admin_cannot_promote_to_owner():
    """Verify an ADMIN actor cannot promote another member to OWNER."""
    ws_id = uuid.uuid4()
    admin_actor_id = uuid.uuid4()
    target_member_id = uuid.uuid4()
    target_user_id = uuid.uuid4()

    member_repo = MagicMock()
    workspace_repo = MagicMock()
    service = WorkspaceMembershipService(member_repo=member_repo, workspace_repo=workspace_repo)

    workspace = Workspace(id=ws_id, name="Test WS", slug="test-ws", status=WorkspaceStatus.ACTIVE.value)
    workspace_repo.get_by_id = AsyncMock(return_value=workspace)

    admin_member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=admin_actor_id,
        role=WorkspaceRole.ADMIN.value,
        status=MemberStatus.ACTIVE.value,
    )
    target_member = WorkspaceMember(
        id=target_member_id,
        workspace_id=ws_id,
        user_id=target_user_id,
        role=WorkspaceRole.MEMBER.value,
        status=MemberStatus.ACTIVE.value,
    )

    member_repo.get_membership = AsyncMock(return_value=admin_member)
    member_repo.get_by_id_for_update = AsyncMock(return_value=target_member)

    session = AsyncMock()

    with pytest.raises(MembershipUnauthorizedError, match="ADMIN cannot promote a member to OWNER"):
        await service.update_member_role(
            session=session,
            workspace_id=ws_id,
            actor_id=admin_actor_id,
            member_id=target_member_id,
            new_role="OWNER",
        )


@pytest.mark.asyncio
async def test_admin_cannot_modify_or_demote_owner():
    """Verify an ADMIN actor cannot modify the role of an OWNER."""
    ws_id = uuid.uuid4()
    admin_actor_id = uuid.uuid4()
    owner_member_id = uuid.uuid4()
    owner_user_id = uuid.uuid4()

    member_repo = MagicMock()
    workspace_repo = MagicMock()
    service = WorkspaceMembershipService(member_repo=member_repo, workspace_repo=workspace_repo)

    workspace = Workspace(id=ws_id, name="Test WS", slug="test-ws", status=WorkspaceStatus.ACTIVE.value)
    workspace_repo.get_by_id = AsyncMock(return_value=workspace)

    admin_member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=admin_actor_id,
        role=WorkspaceRole.ADMIN.value,
        status=MemberStatus.ACTIVE.value,
    )
    owner_member = WorkspaceMember(
        id=owner_member_id,
        workspace_id=ws_id,
        user_id=owner_user_id,
        role=WorkspaceRole.OWNER.value,
        status=MemberStatus.ACTIVE.value,
    )

    member_repo.get_membership = AsyncMock(return_value=admin_member)
    member_repo.get_by_id_for_update = AsyncMock(return_value=owner_member)

    session = AsyncMock()

    with pytest.raises(MembershipUnauthorizedError, match="ADMIN cannot modify the role of an OWNER"):
        await service.update_member_role(
            session=session,
            workspace_id=ws_id,
            actor_id=admin_actor_id,
            member_id=owner_member_id,
            new_role="ADMIN",
        )


@pytest.mark.asyncio
async def test_last_owner_protection_prevents_demotion():
    """Verify that demoting the last remaining active OWNER raises 409 Conflict."""
    ws_id = uuid.uuid4()
    owner1_actor_id = uuid.uuid4()
    owner2_member_id = uuid.uuid4()
    owner2_user_id = uuid.uuid4()

    member_repo = MagicMock()
    workspace_repo = MagicMock()
    service = WorkspaceMembershipService(member_repo=member_repo, workspace_repo=workspace_repo)

    workspace = Workspace(id=ws_id, name="Test WS", slug="test-ws", status=WorkspaceStatus.ACTIVE.value)
    workspace_repo.get_by_id = AsyncMock(return_value=workspace)

    owner1_member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=owner1_actor_id,
        role=WorkspaceRole.OWNER.value,
        status=MemberStatus.ACTIVE.value,
    )
    owner2_member = WorkspaceMember(
        id=owner2_member_id,
        workspace_id=ws_id,
        user_id=owner2_user_id,
        role=WorkspaceRole.OWNER.value,
        status=MemberStatus.ACTIVE.value,
    )

    member_repo.get_membership = AsyncMock(return_value=owner1_member)
    member_repo.get_by_id_for_update = AsyncMock(return_value=owner2_member)
    # Only 1 active owner left in workspace count
    member_repo.count_active_owners = AsyncMock(return_value=1)

    session = AsyncMock()

    with pytest.raises(MembershipConflictError, match="Cannot demote the last remaining OWNER"):
        await service.update_member_role(
            session=session,
            workspace_id=ws_id,
            actor_id=owner1_actor_id,
            member_id=owner2_member_id,
            new_role="ADMIN",
        )
