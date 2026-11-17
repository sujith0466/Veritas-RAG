"""Unit tests for WS-B1: Canonical Role & Membership Authority."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from pydantic import ValidationError

from backend.api.v1.schemas.workspace_member import BulkMemberActionRequest, UpdateMemberRoleRequest
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
    """Verify that UpdateMemberRoleRequest allows only ADMIN and MEMBER and rejects all others."""
    # Permitted assignment roles
    assert UpdateMemberRoleRequest(role="ADMIN").role == "ADMIN"
    assert UpdateMemberRoleRequest(role="MEMBER").role == "MEMBER"

    # Explicitly rejected unassignable roles
    with pytest.raises(ValidationError, match="Direct assignment or promotion to OWNER is not permitted"):
        UpdateMemberRoleRequest(role="OWNER")

    with pytest.raises(ValidationError, match="Role VIEWER is deprecated and cannot be assigned"):
        UpdateMemberRoleRequest(role="VIEWER")

    # Non-canonical / lowercase / whitespace roles must be rejected without normalization
    non_canonical_roles = ["admin", "member", " ADMIN ", " Member ", "Admin"]
    for nc in non_canonical_roles:
        with pytest.raises(ValidationError, match="Noncanonical role value"):
            UpdateMemberRoleRequest(role=nc)

    # Unknown roles must be rejected
    invalid_roles = ["ENGINEER", "ANALYST", "PLATFORM_ADMIN", "superuser", "guest", "random", ""]
    for inv in invalid_roles:
        with pytest.raises(ValidationError):
            UpdateMemberRoleRequest(role=inv)


def test_bulk_member_action_request_validation():
    """Verify BulkMemberActionRequest conditional role validation for update_role."""
    member_id = uuid.uuid4()

    # Valid update_role actions with permitted roles
    req_admin = BulkMemberActionRequest(action="update_role", member_ids=[member_id], role="ADMIN")
    assert req_admin.role == "ADMIN"
    assert req_admin.action == "update_role"

    req_member = BulkMemberActionRequest(action="update_role", member_ids=[member_id], role="MEMBER")
    assert req_member.role == "MEMBER"

    # Missing role when action is update_role
    with pytest.raises(ValidationError, match="Field 'role' is required when action is 'update_role'"):
        BulkMemberActionRequest(action="update_role", member_ids=[member_id], role=None)

    with pytest.raises(ValidationError, match="Field 'role' is required when action is 'update_role'"):
        BulkMemberActionRequest(action="update_role", member_ids=[member_id])

    # Rejection of OWNER and VIEWER in bulk operations
    with pytest.raises(ValidationError, match="Direct assignment or promotion to OWNER is not permitted in bulk operations"):
        BulkMemberActionRequest(action="update_role", member_ids=[member_id], role="OWNER")

    with pytest.raises(ValidationError, match="Role VIEWER is deprecated and cannot be assigned in bulk operations"):
        BulkMemberActionRequest(action="update_role", member_ids=[member_id], role="VIEWER")

    # Rejection of noncanonical role representations
    with pytest.raises(ValidationError, match="Noncanonical role value"):
        BulkMemberActionRequest(action="update_role", member_ids=[member_id], role="admin")

    with pytest.raises(ValidationError):
        BulkMemberActionRequest(action="update_role", member_ids=[member_id], role="ENGINEER")

    # Other bulk actions unaffected by conditional role requirement
    for act in ["suspend", "restore", "remove"]:
        req = BulkMemberActionRequest(action=act, member_ids=[member_id])
        assert req.action == act
        assert req.role is None


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


@pytest.mark.asyncio
async def test_service_direct_assignment_admin_and_member_succeeds():
    """Verify that an authorized OWNER can assign canonical ADMIN and MEMBER roles."""
    ws_id = uuid.uuid4()
    owner_actor_id = uuid.uuid4()
    target_member_id = uuid.uuid4()
    target_user_id = uuid.uuid4()

    member_repo = MagicMock()
    workspace_repo = MagicMock()
    service = WorkspaceMembershipService(member_repo=member_repo, workspace_repo=workspace_repo)

    workspace = Workspace(id=ws_id, name="Test WS", slug="test-ws", status=WorkspaceStatus.ACTIVE.value)
    workspace_repo.get_by_id = AsyncMock(return_value=workspace)

    owner_member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=owner_actor_id,
        role=WorkspaceRole.OWNER.value,
        status=MemberStatus.ACTIVE.value,
    )
    target_member = WorkspaceMember(
        id=target_member_id,
        workspace_id=ws_id,
        user_id=target_user_id,
        role=WorkspaceRole.MEMBER.value,
        status=MemberStatus.ACTIVE.value,
    )

    member_repo.get_membership = AsyncMock(return_value=owner_member)
    member_repo.get_by_id_for_update = AsyncMock(return_value=target_member)
    session = AsyncMock()

    # Assign ADMIN
    updated = await service.update_member_role(
        session=session,
        workspace_id=ws_id,
        actor_id=owner_actor_id,
        member_id=target_member_id,
        new_role="ADMIN",
    )
    assert updated.role == "ADMIN"

    # Assign MEMBER
    updated_back = await service.update_member_role(
        session=session,
        workspace_id=ws_id,
        actor_id=owner_actor_id,
        member_id=target_member_id,
        new_role="MEMBER",
    )
    assert updated_back.role == "MEMBER"


@pytest.mark.asyncio
async def test_service_direct_assignment_viewer_rejected():
    """Verify that service-layer validation rejects assignment of deprecated VIEWER role."""
    ws_id = uuid.uuid4()
    owner_actor_id = uuid.uuid4()
    target_member_id = uuid.uuid4()

    member_repo = MagicMock()
    workspace_repo = MagicMock()
    service = WorkspaceMembershipService(member_repo=member_repo, workspace_repo=workspace_repo)

    workspace = Workspace(id=ws_id, name="Test WS", slug="test-ws", status=WorkspaceStatus.ACTIVE.value)
    workspace_repo.get_by_id = AsyncMock(return_value=workspace)

    owner_member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=owner_actor_id,
        role=WorkspaceRole.OWNER.value,
        status=MemberStatus.ACTIVE.value,
        version=1,
    )
    member_repo.get_membership = AsyncMock(return_value=owner_member)
    session = AsyncMock()

    with pytest.raises(MembershipError, match="Role VIEWER is deprecated and cannot be assigned"):
        await service.update_member_role(
            session=session,
            workspace_id=ws_id,
            actor_id=owner_actor_id,
            member_id=target_member_id,
            new_role="VIEWER",
        )


@pytest.mark.asyncio
async def test_service_direct_assignment_owner_rejected():
    """Verify that direct assignment or promotion to OWNER is rejected at service layer."""
    ws_id = uuid.uuid4()
    owner_actor_id = uuid.uuid4()
    target_member_id = uuid.uuid4()
    target_user_id = uuid.uuid4()

    member_repo = MagicMock()
    workspace_repo = MagicMock()
    service = WorkspaceMembershipService(member_repo=member_repo, workspace_repo=workspace_repo)

    workspace = Workspace(id=ws_id, name="Test WS", slug="test-ws", status=WorkspaceStatus.ACTIVE.value)
    workspace_repo.get_by_id = AsyncMock(return_value=workspace)

    owner_member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=owner_actor_id,
        role=WorkspaceRole.OWNER.value,
        status=MemberStatus.ACTIVE.value,
        version=1,
    )
    target_member = WorkspaceMember(
        id=target_member_id,
        workspace_id=ws_id,
        user_id=target_user_id,
        role=WorkspaceRole.MEMBER.value,
        status=MemberStatus.ACTIVE.value,
        version=1,
    )

    member_repo.get_membership = AsyncMock(return_value=owner_member)
    member_repo.get_by_id_for_update = AsyncMock(return_value=target_member)
    session = AsyncMock()

    with pytest.raises(MembershipError, match="Direct assignment or promotion to OWNER is not permitted"):
        await service.update_member_role(
            session=session,
            workspace_id=ws_id,
            actor_id=owner_actor_id,
            member_id=target_member_id,
            new_role="OWNER",
        )


@pytest.mark.asyncio
async def test_service_rejects_unknown_and_noncanonical_roles():
    """Verify that service-layer validation rejects noncanonical or unknown roles."""
    ws_id = uuid.uuid4()
    owner_actor_id = uuid.uuid4()
    target_member_id = uuid.uuid4()

    member_repo = MagicMock()
    workspace_repo = MagicMock()
    service = WorkspaceMembershipService(member_repo=member_repo, workspace_repo=workspace_repo)

    workspace = Workspace(id=ws_id, name="Test WS", slug="test-ws", status=WorkspaceStatus.ACTIVE.value)
    workspace_repo.get_by_id = AsyncMock(return_value=workspace)

    owner_member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=owner_actor_id,
        role=WorkspaceRole.OWNER.value,
        status=MemberStatus.ACTIVE.value,
        version=1,
    )
    member_repo.get_membership = AsyncMock(return_value=owner_member)
    session = AsyncMock()

    # Lowercase must be rejected without silent normalization
    with pytest.raises(MembershipError, match="Noncanonical role value"):
        await service.update_member_role(
            session=session,
            workspace_id=ws_id,
            actor_id=owner_actor_id,
            member_id=target_member_id,
            new_role="admin",
        )

    # Whitespace must be rejected without silent normalization
    with pytest.raises(MembershipError, match="Noncanonical role value"):
        await service.update_member_role(
            session=session,
            workspace_id=ws_id,
            actor_id=owner_actor_id,
            member_id=target_member_id,
            new_role=" MEMBER ",
        )

    # Unknown role
    with pytest.raises(MembershipError, match="Invalid workspace role"):
        await service.update_member_role(
            session=session,
            workspace_id=ws_id,
            actor_id=owner_actor_id,
            member_id=target_member_id,
            new_role="ENGINEER",
        )


@pytest.mark.asyncio
async def test_service_bulk_update_role_conditional_and_service_validation():
    """Verify bulk update_role behavior with valid roles, invalid roles, and missing role."""
    ws_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    target_id1 = uuid.uuid4()
    target_id2 = uuid.uuid4()

    member_repo = MagicMock()
    workspace_repo = MagicMock()
    service = WorkspaceMembershipService(member_repo=member_repo, workspace_repo=workspace_repo)
    session = AsyncMock()

    workspace = Workspace(id=ws_id, name="Test WS", slug="test-ws", status=WorkspaceStatus.ACTIVE.value)
    workspace_repo.get_by_id = AsyncMock(return_value=workspace)

    owner_member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=actor_id,
        role=WorkspaceRole.OWNER.value,
        status=MemberStatus.ACTIVE.value,
        version=1,
    )
    target_member1 = WorkspaceMember(
        id=target_id1,
        workspace_id=ws_id,
        user_id=uuid.uuid4(),
        role=WorkspaceRole.MEMBER.value,
        status=MemberStatus.ACTIVE.value,
        version=1,
    )
    member_repo.get_membership = AsyncMock(return_value=owner_member)
    member_repo.get_by_id_for_update = AsyncMock(return_value=target_member1)

    # 1. Missing role when action is update_role
    res_missing = await service.bulk_update_members(
        session=session,
        workspace_id=ws_id,
        actor_id=actor_id,
        member_ids=[target_id1],
        action="update_role",
        role=None,
    )
    assert res_missing["total"] == 1
    assert res_missing["results"][0]["status"] == "error"
    assert "Role is required when action is 'update_role'" in res_missing["results"][0]["message"]

    # 2. Invalid role VIEWER in bulk
    res_viewer = await service.bulk_update_members(
        session=session,
        workspace_id=ws_id,
        actor_id=actor_id,
        member_ids=[target_id1],
        action="update_role",
        role="VIEWER",
    )
    assert res_viewer["results"][0]["status"] == "error"
    assert "VIEWER is deprecated" in res_viewer["results"][0]["message"]

    # 3. Invalid role OWNER in bulk
    res_owner = await service.bulk_update_members(
        session=session,
        workspace_id=ws_id,
        actor_id=actor_id,
        member_ids=[target_id1],
        action="update_role",
        role="OWNER",
    )
    assert res_owner["results"][0]["status"] == "error"
    assert "promotion to OWNER is not permitted" in res_owner["results"][0]["message"]

    # 4. Valid role ADMIN in bulk succeeds
    res_admin = await service.bulk_update_members(
        session=session,
        workspace_id=ws_id,
        actor_id=actor_id,
        member_ids=[target_id1],
        action="update_role",
        role="ADMIN",
    )
    assert res_admin["results"][0]["status"] == "success"
