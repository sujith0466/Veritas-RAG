import datetime
from unittest.mock import AsyncMock, MagicMock
import uuid
import pytest

from backend.modules.analytics.models.workspace_usage import WorkspaceUsage
from backend.modules.analytics.repositories.usage_repository import UsageRepository


def test_period_start_calculation():
    dt = datetime.datetime(2026, 8, 19, 14, 30, 0, tzinfo=datetime.timezone.utc)
    res = UsageRepository.get_current_period_start(dt)
    assert res == datetime.date(2026, 8, 1)

    d = datetime.date(2026, 12, 25)
    res2 = UsageRepository.get_current_period_start(d)
    assert res2 == datetime.date(2026, 12, 1)


@pytest.mark.asyncio
async def test_atomic_increment_negative_tokens_raises_value_error():
    session = AsyncMock()
    repo = UsageRepository(session)
    ws_id = uuid.uuid4()

    with pytest.raises(ValueError) as exc:
        await repo.atomic_increment(workspace_id=ws_id, tokens=-10, queries=1)
    assert "non-negative" in str(exc.value)

    with pytest.raises(ValueError) as exc2:
        await repo.atomic_increment(workspace_id=ws_id, tokens=100, queries=-1)
    assert "non-negative" in str(exc2.value)


@pytest.mark.asyncio
async def test_atomic_increment_execution():
    session = AsyncMock()
    ws_id = uuid.uuid4()
    p_start = datetime.date(2026, 8, 1)

    expected = WorkspaceUsage(
        workspace_id=ws_id,
        billing_period_start=p_start,
        used_tokens=500,
        used_queries=2,
    )
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = expected
    session.execute = AsyncMock(return_value=mock_result)
    session.commit = AsyncMock()

    repo = UsageRepository(session)
    usage = await repo.atomic_increment(workspace_id=ws_id, tokens=500, queries=2, period_start=p_start)

    assert usage.used_tokens == 500
    assert usage.used_queries == 2
    session.execute.assert_called_once()
    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_get_current_period_usage():
    session = AsyncMock()
    ws_id = uuid.uuid4()
    p_start = datetime.date(2026, 8, 1)

    expected = WorkspaceUsage(
        workspace_id=ws_id,
        billing_period_start=p_start,
        used_tokens=1500,
        used_queries=10,
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = expected
    session.execute = AsyncMock(return_value=mock_result)

    repo = UsageRepository(session)
    usage = await repo.get_current_period_usage(workspace_id=ws_id, period_start=p_start)

    assert usage is not None
    assert usage.used_tokens == 1500
    session.execute.assert_called_once()
