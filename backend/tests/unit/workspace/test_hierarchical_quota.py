"""Unit tests for WS-B7: Hierarchical Quota Enforcement."""

import uuid
from unittest.mock import AsyncMock, MagicMock
import pytest

from backend.modules.analytics.models.tenant_quota import TenantQuotaORM
from backend.modules.analytics.models.workspace_user_quota import WorkspaceUserQuotaORM
from backend.modules.analytics.schemas.errors import QuotaExceededError
from backend.modules.analytics.services.quota import QuotaGovernor


@pytest.mark.asyncio
async def test_hierarchical_quota_allowed_when_within_limits():
    """Verify check_hierarchical_quota allows usage when within both workspace and user caps."""
    governor = QuotaGovernor()
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()

    # Workspace limit: 1,000,000; Used: 100,000
    mock_ws_quota = TenantQuotaORM(
        tenant_id=str(ws_id),
        workspace_id=ws_id,
        monthly_token_limit=1_000_000,
        monthly_budget_usd=150.0,
        is_hard_enforced=True,
    )
    governor.get_quota_settings = AsyncMock(return_value=mock_ws_quota)
    governor.get_durable_usage = AsyncMock(return_value=100_000)

    # User cap: 50,000; Used: 10,000
    mock_user_quota = WorkspaceUserQuotaORM(
        workspace_id=ws_id,
        user_id=user_id,
        monthly_token_budget=50_000,
        is_hard_enforced=True,
    )
    governor.get_user_durable_usage = AsyncMock(return_value=10_000)

    mock_repo = MagicMock()
    mock_repo.get_user_quota = AsyncMock(return_value=mock_user_quota)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "backend.modules.analytics.repositories.user_quota_repository.UserQuotaRepository.get_user_quota",
            mock_repo.get_user_quota,
        )

        res = await governor.check_hierarchical_quota(
            workspace_id=ws_id,
            user_id=user_id,
            requested_tokens=5_000,
        )

        assert res.is_allowed is True
        assert res.blocked_by is None
        assert res.user_used_tokens == 10_000
        assert res.user_token_limit == 50_000
        assert res.workspace_used_tokens == 100_000
        assert res.workspace_token_limit == 1_000_000


@pytest.mark.asyncio
async def test_hierarchical_quota_blocks_when_user_cap_exceeded():
    """Verify check_hierarchical_quota blocks when user cap is exceeded, even if workspace has capacity."""
    governor = QuotaGovernor()
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()

    # Workspace limit: 1,000,000; Used: 100,000 (Plenty of capacity)
    mock_ws_quota = TenantQuotaORM(
        tenant_id=str(ws_id),
        workspace_id=ws_id,
        monthly_token_limit=1_000_000,
        monthly_budget_usd=150.0,
        is_hard_enforced=True,
    )
    governor.get_quota_settings = AsyncMock(return_value=mock_ws_quota)
    governor.get_durable_usage = AsyncMock(return_value=100_000)

    # User cap: 50,000; Used: 48,000 -> Requesting 5,000 will exceed 50,000
    mock_user_quota = WorkspaceUserQuotaORM(
        workspace_id=ws_id,
        user_id=user_id,
        monthly_token_budget=50_000,
        is_hard_enforced=True,
    )
    governor.get_user_durable_usage = AsyncMock(return_value=48_000)

    mock_repo = MagicMock()
    mock_repo.get_user_quota = AsyncMock(return_value=mock_user_quota)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "backend.modules.analytics.repositories.user_quota_repository.UserQuotaRepository.get_user_quota",
            mock_repo.get_user_quota,
        )

        res = await governor.check_hierarchical_quota(
            workspace_id=ws_id,
            user_id=user_id,
            requested_tokens=5_000,
        )

        assert res.is_allowed is False
        assert res.blocked_by == "user_quota"
        assert "User monthly token budget exhausted" in res.detail

        # enforce_hierarchical_quota must raise QuotaExceededError
        with pytest.raises(QuotaExceededError, match="User monthly token budget exhausted"):
            await governor.enforce_hierarchical_quota(
                workspace_id=ws_id,
                user_id=user_id,
                requested_tokens=5_000,
            )


@pytest.mark.asyncio
async def test_hierarchical_quota_blocks_when_workspace_cap_exceeded():
    """Verify check_hierarchical_quota blocks when workspace limit is exhausted, regardless of user cap."""
    governor = QuotaGovernor()
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()

    # Workspace limit: 1,000,000; Used: 998,000 -> Requesting 5,000 will exceed
    mock_ws_quota = TenantQuotaORM(
        tenant_id=str(ws_id),
        workspace_id=ws_id,
        monthly_token_limit=1_000_000,
        monthly_budget_usd=150.0,
        is_hard_enforced=True,
    )
    governor.get_quota_settings = AsyncMock(return_value=mock_ws_quota)
    governor.get_durable_usage = AsyncMock(return_value=998_000)

    res = await governor.check_hierarchical_quota(
        workspace_id=ws_id,
        user_id=user_id,
        requested_tokens=5_000,
    )

    assert res.is_allowed is False
    assert res.blocked_by == "workspace_quota"
    assert "Workspace token budget exhausted" in res.detail


@pytest.mark.asyncio
async def test_other_user_not_blocked_by_user_quota():
    """Verify user B is NOT blocked when user A has exhausted their personal quota."""
    governor = QuotaGovernor()
    ws_id = uuid.uuid4()
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()

    mock_ws_quota = TenantQuotaORM(
        tenant_id=str(ws_id),
        workspace_id=ws_id,
        monthly_token_limit=1_000_000,
        monthly_budget_usd=150.0,
        is_hard_enforced=True,
    )
    governor.get_quota_settings = AsyncMock(return_value=mock_ws_quota)
    governor.get_durable_usage = AsyncMock(return_value=200_000)

    # User A has 50k cap and 50k used (exhausted)
    quota_a = WorkspaceUserQuotaORM(
        workspace_id=ws_id,
        user_id=user_a,
        monthly_token_budget=50_000,
        is_hard_enforced=True,
    )
    # User B has NO cap (None, inherits workspace)
    quota_b = None

    async def fake_get_user_quota(self, wid, uid):
        return quota_a if uid == user_a else quota_b

    async def fake_get_user_usage(wid, uid, session=None):
        return 50_000 if uid == user_a else 5_000

    governor.get_user_durable_usage = AsyncMock(side_effect=fake_get_user_usage)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "backend.modules.analytics.repositories.user_quota_repository.UserQuotaRepository.get_user_quota",
            fake_get_user_quota,
        )

        # Check User A -> BLOCKED
        res_a = await governor.check_hierarchical_quota(
            workspace_id=ws_id,
            user_id=user_a,
            requested_tokens=100,
        )
        assert res_a.is_allowed is False
        assert res_a.blocked_by == "user_quota"

        # Check User B -> ALLOWED
        res_b = await governor.check_hierarchical_quota(
            workspace_id=ws_id,
            user_id=user_b,
            requested_tokens=100,
        )
        assert res_b.is_allowed is True
        assert res_b.blocked_by is None
