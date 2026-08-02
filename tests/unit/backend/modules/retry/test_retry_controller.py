"""Unit tests for RetryController monotonicity and hard cap — Phase 7."""
import pytest

from backend.modules.retry.schemas.retry_dto import RetryAction, RetryReason, RetryRequestContextDTO
from backend.modules.retry.services.retry_controller import RetryController


@pytest.mark.asyncio
async def test_monotonic_regression_triggers_abort():
    """Score drops from 70 → 60: must ABORT with is_monotonic_regression=True."""
    controller = RetryController()
    qid = "q_mono_regression"

    # Attempt 1: score=70.0 recorded, no prior history → should NOT abort on monotonicity
    ctx1 = RetryRequestContextDTO(
        query_id=qid, tenant_id="t1", attempt_number=1,
        reason=RetryReason.LOW_CONFIDENCE,
        last_confidence_score=70.0,
    )
    d1 = await controller.handle_retry(ctx1)
    assert d1.is_monotonic_regression is False

    # Attempt 2: score=60.0 (worse than 70.0) → ABORT
    ctx2 = RetryRequestContextDTO(
        query_id=qid, tenant_id="t1", attempt_number=2,
        reason=RetryReason.LOW_CONFIDENCE,
        last_confidence_score=60.0,
    )
    d2 = await controller.handle_retry(ctx2)
    assert d2.action == RetryAction.ABORT
    assert d2.is_monotonic_regression is True


@pytest.mark.asyncio
async def test_monotonic_improvement_continues():
    """Score rises from 55 → 70: should NOT abort on monotonicity."""
    controller = RetryController()
    qid = "q_mono_improvement"

    ctx1 = RetryRequestContextDTO(
        query_id=qid, tenant_id="t1", attempt_number=1,
        reason=RetryReason.LOW_CONFIDENCE,
        last_confidence_score=55.0,
    )
    await controller.handle_retry(ctx1)

    ctx2 = RetryRequestContextDTO(
        query_id=qid, tenant_id="t1", attempt_number=2,
        reason=RetryReason.LOW_CONFIDENCE,
        last_confidence_score=70.0,
    )
    d2 = await controller.handle_retry(ctx2)
    assert d2.is_monotonic_regression is False


@pytest.mark.asyncio
async def test_hard_cap_enforced_at_attempt_4():
    """Attempt 4 must be rejected regardless of reason (hard cap = 3)."""
    controller = RetryController()
    ctx = RetryRequestContextDTO(
        query_id="q_cap", tenant_id="t1",
        attempt_number=4,
        reason=RetryReason.LLM_API_ERROR,
    )
    d = await controller.handle_retry(ctx)
    assert d.action == RetryAction.ABORT
    assert d.is_budget_exhausted is True


@pytest.mark.asyncio
async def test_no_history_no_regression():
    """When no prior score exists, no regression should be flagged."""
    controller = RetryController()
    ctx = RetryRequestContextDTO(
        query_id="q_fresh", tenant_id="t1", attempt_number=1,
        reason=RetryReason.LOW_CONFIDENCE,
        last_confidence_score=None,
    )
    d = await controller.handle_retry(ctx)
    assert d.is_monotonic_regression is False
