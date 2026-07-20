"""Unit tests for DecisionEngine — Phase 7."""
import pytest
from backend.modules.retry.schemas.retry_dto import RetryRequestContextDTO, RetryReason, RetryAction
from backend.modules.retry.services.decision_engine import DecisionEngine


@pytest.mark.asyncio
async def test_rate_limit_gets_backoff_action():
    engine = DecisionEngine()
    ctx = RetryRequestContextDTO(
        query_id="q1", tenant_id="t1", attempt_number=1,
        reason=RetryReason.RATE_LIMIT,
    )
    decision = await engine.decide(ctx)
    assert decision.action == RetryAction.RETRY_WITH_BACKOFF
    # attempt=1 → 1000 * 2^(1-1) = 1000
    assert decision.backoff_ms == 1000


@pytest.mark.asyncio
async def test_exponential_backoff_increases_on_second_attempt():
    engine = DecisionEngine()
    ctx = RetryRequestContextDTO(
        query_id="q1", tenant_id="t1", attempt_number=2,
        reason=RetryReason.RATE_LIMIT,
    )
    d2 = await engine.decide(ctx)
    # 1000 * 2^(2-1) = 2000
    assert d2.backoff_ms == 2000


@pytest.mark.asyncio
async def test_budget_exhausted_aborts():
    engine = DecisionEngine()
    ctx = RetryRequestContextDTO(
        query_id="q_ex", tenant_id="t1",
        attempt_number=4,   # > hard cap of 3
        reason=RetryReason.RATE_LIMIT,
    )
    decision = await engine.decide(ctx)
    assert decision.action == RetryAction.ABORT
    assert decision.is_budget_exhausted is True


@pytest.mark.asyncio
async def test_low_confidence_gets_rewrite_action():
    engine = DecisionEngine()
    ctx = RetryRequestContextDTO(
        query_id="q2", tenant_id="t1", attempt_number=1,
        reason=RetryReason.LOW_CONFIDENCE,
    )
    decision = await engine.decide(ctx)
    assert decision.action == RetryAction.RETRY_WITH_REWRITE


@pytest.mark.asyncio
async def test_timeout_gets_fallback_model_action():
    engine = DecisionEngine()
    ctx = RetryRequestContextDTO(
        query_id="q3", tenant_id="t1", attempt_number=1,
        reason=RetryReason.TIMEOUT,
    )
    decision = await engine.decide(ctx)
    assert decision.action == RetryAction.RETRY_WITH_FALLBACK_MODEL
