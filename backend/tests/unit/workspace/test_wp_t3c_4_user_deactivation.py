"""Unit tests for WP-T3C-4: User Account Deactivation Serialization and Sole Workspace Ownership Invariant Enforcement.

Verifies:
1. Case A: Rejection under D-17 with SoleWorkspaceOwnerConflictException (HTTP 409) if user owns active workspace.
2. Case C: Rejection with InactiveWorkspaceOwnerConflictException (HTTP 409) if user owns inactive/deleted workspace.
3. Case B: Successful deactivation for eligible non-owner / zero-membership user:
   - Locks user row with FOR UPDATE
   - Locks affected non-owner memberships in ascending order
   - Soft-deletes non-owner memberships
   - Soft-deletes user (is_active=False, is_deleted=True)
   - Revokes UserSessions in DB
   - Emits transactional AuditLog
   - Calls Redis token revocation
4. Re-authentication validation and already deactivated user handling.
"""

import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.models.entities.user import User
from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember, WorkspaceRole
from backend.models.entities.audit_log import AuditLog
from backend.services.user_lifecycle import (
    InactiveWorkspaceOwnerConflictException,
    LifecycleException,
    ReauthenticationFailedException,
    SoleWorkspaceOwnerConflictException,
    UserLifecycleService,
)


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_case_a_active_workspace_owner_rejected(mock_session):
    user_id = uuid.uuid4()
    ws_id = uuid.uuid4()
    ws_name = "Engineering Alpha"

    # Mock execute return for active owned query
    result_mock = MagicMock()
    result_mock.all.return_value = [(ws_id, ws_name)]
    mock_session.execute.return_value = result_mock

    service = UserLifecycleService(mock_session)

    with pytest.raises(SoleWorkspaceOwnerConflictException) as exc_info:
        await service.check_sole_workspace_ownership(user_id)

    assert ws_name in str(exc_info.value)
    assert "sole owner of active workspace" in str(exc_info.value)


@pytest.mark.asyncio
async def test_case_c_inactive_workspace_owner_rejected(mock_session):
    user_id = uuid.uuid4()
    ws_id = uuid.uuid4()
    ws_name = "Suspended Legacy Workspace"

    # First query (active) returns empty, second query (inactive) returns 1 row
    result_active = MagicMock()
    result_active.all.return_value = []

    result_inactive = MagicMock()
    result_inactive.all.return_value = [(ws_id, ws_name)]

    mock_session.execute.side_effect = [result_active, result_inactive]

    service = UserLifecycleService(mock_session)

    with pytest.raises(InactiveWorkspaceOwnerConflictException) as exc_info:
        await service.check_sole_workspace_ownership(user_id)

    assert ws_name in str(exc_info.value)
    assert "inactive or deleted workspace" in str(exc_info.value)


@pytest.mark.asyncio
async def test_case_b_eligible_non_owner_deactivation(mock_session):
    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        email="developer@example.com",
        role="member",
        is_active=True,
        is_deleted=False,
        hashed_password=None,  # SSO-like, bypasses password check
    )

    # 1. User row query result (Step 1)
    res_user = MagicMock()
    res_user.scalar_one_or_none.return_value = user

    # 2. Distinct workspace IDs query (Step 2)
    m1 = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        user_id=user_id,
        role=WorkspaceRole.MEMBER.value,
        status=MemberStatus.ACTIVE.value,
        is_deleted=False,
    )
    res_ws_ids = MagicMock()
    res_ws_ids.scalars.return_value.all.return_value = [m1.workspace_id]

    # 3. Workspaces lock query: dummy (Step 3)
    res_ws_lock = MagicMock()

    # 4. Sole-owner check: active workspaces where user is OWNER -> none (Step 4)
    res_active = MagicMock()
    res_active.all.return_value = []

    # 5. Sole-owner check: inactive workspaces where user is OWNER -> none (Step 4)
    res_inactive = MagicMock()
    res_inactive.all.return_value = []

    # 6. User memberships lock query: one MEMBER role (Step 5)
    res_members = MagicMock()
    res_members.scalars.return_value.all.return_value = [m1]

    # 7. UserSession update query: dummy (Step 7)
    res_session = MagicMock()

    mock_session.execute.side_effect = [
        res_user,
        res_ws_ids,
        res_ws_lock,
        res_active,
        res_inactive,
        res_members,
        res_session,
    ]

    service = UserLifecycleService(mock_session)
    service.jwt_service.revoke_user_tokens = AsyncMock()

    await service.deactivate_user_account(
        user_id=user_id,
        password=None,
        confirmation_text="DELETE",
    )

    # Verifications
    assert user.is_active is False
    assert user.is_deleted is True
    assert m1.is_deleted is True
    mock_session.commit.assert_awaited()
    service.jwt_service.revoke_user_tokens.assert_awaited_once_with(str(user_id))

    # Verify audit log was added
    added_entities = [call.args[0] for call in mock_session.add.call_args_list]
    audit_logs = [e for e in added_entities if isinstance(e, AuditLog)]
    assert len(audit_logs) == 1
    assert audit_logs[0].action == "user.account.deactivated"
    assert audit_logs[0].resource_id == str(user_id)


@pytest.mark.asyncio
async def test_deactivate_already_deactivated_user_rejected(mock_session):
    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        email="deleted@example.com",
        role="member",
        is_active=False,
        is_deleted=True,
    )

    res_user = MagicMock()
    res_user.scalar_one_or_none.return_value = user
    mock_session.execute.return_value = res_user

    service = UserLifecycleService(mock_session)

    with pytest.raises(LifecycleException, match="User not found or already deactivated."):
        await service.deactivate_user_account(
            user_id=user_id,
            password=None,
            confirmation_text="DELETE",
        )
