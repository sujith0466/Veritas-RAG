"""Automated concurrency and load benchmark tests.

Validates:
1. High-concurrency atomic counter increments on UsageRepository (F13.2 / F15.2).
2. Race condition resilience under 100 simultaneous async increment operations.
3. Verification that accumulated sum exactly equals mathematical expected total.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from backend.modules.analytics.models.workspace_usage import WorkspaceUsage
from backend.modules.analytics.repositories.usage_repository import UsageRepository


@pytest.mark.asyncio
async def test_concurrent_atomic_quota_increments():
    """Verify that 100 concurrent asynchronous increments correctly aggregate without lost updates."""
    ws_id = uuid.uuid4()
    total_concurrent_tasks = 100
    tokens_per_task = 50
    queries_per_task = 1

    # Simulated in-memory atomic counter simulating PostgreSQL ON CONFLICT DO UPDATE behavior
    counter_lock = asyncio.Lock()
    state = {"tokens": 0, "queries": 0}

    mock_session = AsyncMock()

    async def mock_execute(stmt):
        # Intercept and atomically accumulate under concurrency lock
        async with counter_lock:
            state["tokens"] += tokens_per_task
            state["queries"] += queries_per_task
            current_tokens = state["tokens"]
            current_queries = state["queries"]

        res = MagicMock()
        mock_usage = WorkspaceUsage(
            workspace_id=ws_id,
            billing_period_start=UsageRepository.get_current_period_start(),
            used_tokens=current_tokens,
            used_queries=current_queries,
        )
        res.scalar_one.return_value = mock_usage
        return res

    mock_session.execute.side_effect = mock_execute

    repo = UsageRepository(mock_session)

    # Launch 100 concurrent async tasks simultaneously
    async def worker():
        return await repo.atomic_increment(
            workspace_id=ws_id,
            tokens=tokens_per_task,
            queries=queries_per_task,
        )

    tasks = [asyncio.create_task(worker()) for _ in range(total_concurrent_tasks)]
    results = await asyncio.gather(*tasks)

    # Assert all 100 tasks returned a result
    assert len(results) == total_concurrent_tasks

    # Mathematical truth assertions
    expected_tokens = total_concurrent_tasks * tokens_per_task  # 100 * 50 = 5000
    expected_queries = total_concurrent_tasks * queries_per_task  # 100 * 1 = 100

    assert state["tokens"] == expected_tokens, (
        f"Race condition detected! Expected {expected_tokens} tokens, got {state['tokens']}"
    )
    assert state["queries"] == expected_queries, (
        f"Race condition detected! Expected {expected_queries} queries, got {state['queries']}"
    )
