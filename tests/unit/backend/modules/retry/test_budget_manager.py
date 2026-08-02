"""Unit tests for RetryBudgetManager."""
import pytest

from backend.modules.retry.services.budget_manager import RetryBudgetManager


@pytest.mark.asyncio
async def test_budget_within_cap():
    mgr = RetryBudgetManager()
    assert await mgr.check_budget("t1", "q1", 1) is True
    assert await mgr.check_budget("t1", "q1", 3) is True


@pytest.mark.asyncio
async def test_budget_at_cap_boundary():
    mgr = RetryBudgetManager()
    # Exactly at cap = 3 is still OK
    assert await mgr.check_budget("t1", "q1", 3) is True


@pytest.mark.asyncio
async def test_budget_exceeds_cap():
    mgr = RetryBudgetManager()
    # 4 and beyond is exhausted (hard cap = 3)
    assert await mgr.check_budget("t1", "q1", 4) is False
    assert await mgr.check_budget("t1", "q1", 99) is False
