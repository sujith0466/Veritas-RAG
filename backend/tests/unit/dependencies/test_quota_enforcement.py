from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import pytest
from fastapi import HTTPException

from backend.core.auth.context import UserContext
from backend.core.dependencies.quota import enforce_workspace_quota
from backend.core.dependencies.workspace import get_workspace_member_or_raise
from backend.core.permissions.rbac import Role
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember


@pytest.mark.asyncio
async def test_quota_guard_under_limit_passes():
    ws_id = uuid.uuid4()
    user = UserContext(id=uuid.uuid4(), email="user@example.com", role=Role.ADMIN.value, workspace_id=ws_id)
    session = AsyncMock()

    guard = enforce_workspace_quota()

    with patch("backend.core.dependencies.quota.get_workspace_member_or_raise", new_callable=AsyncMock) as mock_auth, \
         patch("backend.core.dependencies.quota.QuotaGovernor") as mock_gov_cls:
        gov_instance = MagicMock()
        gov_instance.check_quota = AsyncMock(return_value=(False, 500, 10000, True))
        mock_gov_cls.return_value = gov_instance

        # Should not raise
        await guard(workspace_id=ws_id, current_user=user, session=session)
        mock_auth.assert_called_once_with(ws_id, user, session)
        gov_instance.check_quota.assert_called_once()


@pytest.mark.asyncio
async def test_quota_guard_at_limit_hard_enforced_raises_429():
    ws_id = uuid.uuid4()
    user = UserContext(id=uuid.uuid4(), email="user@example.com", role=Role.ADMIN.value, workspace_id=ws_id)
    session = AsyncMock()

    guard = enforce_workspace_quota()

    with patch("backend.core.dependencies.quota.get_workspace_member_or_raise", new_callable=AsyncMock), \
         patch("backend.core.dependencies.quota.QuotaGovernor") as mock_gov_cls:
        gov_instance = MagicMock()
        gov_instance.check_quota = AsyncMock(return_value=(True, 10000, 10000, True))
        mock_gov_cls.return_value = gov_instance

        with pytest.raises(HTTPException) as exc_info:
            await guard(workspace_id=ws_id, current_user=user, session=session)

        assert exc_info.value.status_code == 429
        assert "Workspace token quota exceeded" in exc_info.value.detail
        assert exc_info.value.headers.get("Retry-After") == "3600"


@pytest.mark.asyncio
async def test_quota_guard_at_limit_soft_enforced_passes():
    ws_id = uuid.uuid4()
    user = UserContext(id=uuid.uuid4(), email="user@example.com", role=Role.ADMIN.value, workspace_id=ws_id)
    session = AsyncMock()

    guard = enforce_workspace_quota()

    with patch("backend.core.dependencies.quota.get_workspace_member_or_raise", new_callable=AsyncMock), \
         patch("backend.core.dependencies.quota.QuotaGovernor") as mock_gov_cls:
        gov_instance = MagicMock()
        # is_exceeded is False because is_hard_enforced=False
        gov_instance.check_quota = AsyncMock(return_value=(False, 12000, 10000, False))
        mock_gov_cls.return_value = gov_instance

        # Should not raise because soft-enforced
        await guard(workspace_id=ws_id, current_user=user, session=session)


@pytest.mark.asyncio
async def test_workspace_membership_authorization_active_member_passes():
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    user = UserContext(id=user_id, email="member@example.com", role=Role.MEMBER.value, workspace_id=ws_id)
    session = AsyncMock()

    with patch("backend.core.dependencies.workspace.WorkspaceMemberRepository") as mock_repo_cls:
        repo_instance = MagicMock()
        member = WorkspaceMember(id=uuid.uuid4(), workspace_id=ws_id, user_id=user_id, role="MEMBER", status=MemberStatus.ACTIVE.value)
        repo_instance.get_membership = AsyncMock(return_value=member)
        mock_repo_cls.return_value = repo_instance

        result = await get_workspace_member_or_raise(ws_id, user, session)
        assert result is not None
        assert result.workspace_id == ws_id


@pytest.mark.asyncio
async def test_workspace_membership_authorization_non_member_raises_403():
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    user = UserContext(id=user_id, email="intruder@example.com", role=Role.MEMBER.value, workspace_id=ws_id)
    session = AsyncMock()

    with patch("backend.core.dependencies.workspace.WorkspaceMemberRepository") as mock_repo_cls:
        repo_instance = MagicMock()
        repo_instance.get_membership = AsyncMock(return_value=None)
        mock_repo_cls.return_value = repo_instance

        with pytest.raises(HTTPException) as exc_info:
            await get_workspace_member_or_raise(ws_id, user, session)

        assert exc_info.value.status_code == 403
        assert "Forbidden" in exc_info.value.detail


@pytest.mark.asyncio
async def test_workspace_membership_authorization_platform_admin_bypasses():
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    user = UserContext(id=user_id, email="admin@platform.com", role=Role.PLATFORM_ADMIN.value)
    session = AsyncMock()

    result = await get_workspace_member_or_raise(ws_id, user, session)
    assert result is None
