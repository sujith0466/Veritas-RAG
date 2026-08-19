import datetime
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import pytest

from backend.modules.analytics.models.tenant_quota import TenantQuotaORM
from backend.modules.analytics.models.workspace_usage import WorkspaceUsage
from backend.modules.analytics.services.quota import QuotaGovernor


@pytest.mark.asyncio
async def test_quota_governor_redis_hit():
    governor = QuotaGovernor()
    ws_id = uuid.uuid4()
    session = AsyncMock()

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value="5000")

    with patch("backend.modules.analytics.services.quota.get_redis_client", return_value=mock_redis):
        used = await governor.get_durable_usage(ws_id, session=session)
        assert used == 5000
        mock_redis.get.assert_called_once_with(f"quota:usage:{ws_id}")


@pytest.mark.asyncio
async def test_quota_governor_redis_miss_pg_fallback():
    governor = QuotaGovernor()
    ws_id = uuid.uuid4()
    session = AsyncMock()

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock()

    with patch("backend.modules.analytics.services.quota.get_redis_client", return_value=mock_redis), \
         patch("backend.modules.analytics.services.quota.UsageRepository") as mock_repo_cls:
        repo_instance = MagicMock()
        repo_instance.get_current_period_usage = AsyncMock(return_value=WorkspaceUsage(
            workspace_id=ws_id,
            billing_period_start=datetime.date(2026, 8, 1),
            used_tokens=7500,
            used_queries=15,
        ))
        mock_repo_cls.return_value = repo_instance

        used = await governor.get_durable_usage(ws_id, session=session)
        assert used == 7500
        mock_redis.set.assert_called_once_with(f"quota:usage:{ws_id}", 7500, ex=60)


@pytest.mark.asyncio
async def test_quota_governor_redis_down_pg_fallback():
    governor = QuotaGovernor()
    ws_id = uuid.uuid4()
    session = AsyncMock()

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(
        side_effect=ConnectionError("Redis unavailable")
    )

    with patch("backend.modules.analytics.services.quota.get_redis_client", return_value=mock_redis), \
         patch("backend.modules.analytics.services.quota.UsageRepository") as mock_repo_cls:
        repo_instance = MagicMock()
        repo_instance.get_current_period_usage = AsyncMock(return_value=WorkspaceUsage(
            workspace_id=ws_id,
            billing_period_start=datetime.date(2026, 8, 1),
            used_tokens=3200,
            used_queries=8,
        ))
        mock_repo_cls.return_value = repo_instance

        # Should not raise, should successfully return Graceful PG fallback value
        used = await governor.get_durable_usage(ws_id, session=session)
        assert used == 3200


@pytest.mark.asyncio
async def test_quota_governor_check_quota_exceeded():
    governor = QuotaGovernor()
    ws_id = uuid.uuid4()
    session = AsyncMock()

    quota_settings = TenantQuotaORM(
        tenant_id=str(ws_id),
        workspace_id=ws_id,
        monthly_token_limit=10000,
        monthly_budget_usd=150.0,
        warning_threshold_pct=0.80,
        is_hard_enforced=True,
    )

    governor.get_quota_settings = AsyncMock(return_value=quota_settings)
    governor.get_durable_usage = AsyncMock(return_value=10000)

    in_exceeded, used_tokens, limit, is_hard = await governor.check_quota(ws_id, session=session)
    assert in_exceeded is True
    assert used_tokens == 10000
    assert limit == 10000
    assert is_hard is True


@pytest.mark.asyncio
async def test_quota_governor_check_quota_within_limit():
    governor = QuotaGovernor()
    ws_id = uuid.uuid4()
    session = AsyncMock()

    quota_settings = TenantQuotaORM(
        tenant_id=str(ws_id),
        workspace_id=ws_id,
        monthly_token_limit=10000,
        monthly_budget_usd=150.0,
        warning_threshold_pct=0.80,
        is_hard_enforced=True,
    )

    governor.get_quota_settings = AsyncMock(return_value=quota_settings)
    governor.get_durable_usage = AsyncMock(return_value=3500)

    in_exceeded, used_tokens, limit, is_hard = await governor.check_quota(ws_id, session=session)
    assert in_exceeded is False
    assert used_tokens == 3500
