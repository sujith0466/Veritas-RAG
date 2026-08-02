import os

def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Created {path}")

# __init__.py files
for d in [
    "backend/modules/retry",
    "backend/modules/retry/schemas",
    "backend/modules/retry/services",
    "backend/modules/retry/api",
    "tests/unit/backend/modules/retry",
]:
    os.makedirs(d, exist_ok=True)
    init_path = os.path.join(d, "__init__.py")
    if not os.path.exists(init_path):
        with open(init_path, "w") as f:
            f.write("")
        print(f"Created {init_path}")

# Test: rule engine
test_rule_engine = '''"""Unit tests for RuleEngine."""

from backend.modules.retry.schemas.retry_dto import RetryReason, RetryAction
from backend.modules.retry.services.rule_engine import RuleEngine


def test_rule_engine_rate_limit():
    engine = RuleEngine()
    rule = engine.evaluate(RetryReason.RATE_LIMIT)
    assert rule.action == RetryAction.RETRY_WITH_BACKOFF
    assert rule.base_backoff_ms == 1000


def test_rule_engine_low_confidence():
    engine = RuleEngine()
    rule = engine.evaluate(RetryReason.LOW_CONFIDENCE)
    assert rule.action == RetryAction.RETRY_WITH_REWRITE


def test_rule_engine_unknown_returns_abort():
    engine = RuleEngine()
    rule = engine.evaluate(RetryReason.UNKNOWN)
    assert rule.action == RetryAction.ABORT
'''
write_file("tests/unit/backend/modules/retry/test_rule_engine.py", test_rule_engine)


# Test: budget manager
test_budget = '''"""Unit tests for RetryBudgetManager."""
import pytest
from backend.modules.retry.services.budget_manager import RetryBudgetManager


@pytest.mark.asyncio
async def test_budget_within_cap():
    mgr = RetryBudgetManager()
    assert await mgr.check_budget("t1", "q1", 1) is True
    assert await mgr.check_budget("t1", "q1", 3) is True


@pytest.mark.asyncio
async def test_budget_exceeds_cap():
    mgr = RetryBudgetManager()
    assert await mgr.check_budget("t1", "q1", 4) is False
    assert await mgr.check_budget("t1", "q1", 99) is False
'''
write_file("tests/unit/backend/modules/retry/test_budget_manager.py", test_budget)


# Test: decision engine
test_decision = '''"""Unit tests for DecisionEngine."""
import pytest
from backend.modules.retry.schemas.retry_dto import RetryContextDTO, RetryReason, RetryAction
from backend.modules.retry.services.decision_engine import DecisionEngine


@pytest.mark.asyncio
async def test_decision_engine_rate_limit():
    engine = DecisionEngine()
    ctx = RetryContextDTO(
        query_id="q1",
        tenant_id="t1",
        attempt_number=1,
        reason=RetryReason.RATE_LIMIT,
    )
    decision = await engine.decide(ctx)
    assert decision.action == RetryAction.RETRY_WITH_BACKOFF
    assert decision.backoff_ms == 1000  # 1000 * 2^0


@pytest.mark.asyncio
async def test_decision_engine_budget_exhausted():
    engine = DecisionEngine()
    ctx = RetryContextDTO(
        query_id="q1",
        tenant_id="t1",
        attempt_number=4,          # > hard cap of 3
        reason=RetryReason.RATE_LIMIT,
    )
    decision = await engine.decide(ctx)
    assert decision.action == RetryAction.ABORT
    assert decision.is_budget_exhausted is True
'''
write_file("tests/unit/backend/modules/retry/test_decision_engine.py", test_decision)


# Test: retry controller (monotonicity)
test_controller = '''"""Unit tests for RetryController monotonicity enforcement."""
import pytest
from backend.modules.retry.schemas.retry_dto import RetryContextDTO, RetryReason, RetryAction
from backend.modules.retry.services.retry_controller import RetryController
from backend.modules.confidence.schemas.confidence_dto import (
    ConfidenceResultDTOv2, ConfidenceAction,
    CoverageMetricsDTOv2, EvidenceStrengthDTO,
    FreshnessReportDTOv2, ConflictReportDTOv2,
)


def make_confidence(score: float) -> ConfidenceResultDTOv2:
    return ConfidenceResultDTOv2(
        score=score,
        action=ConfidenceAction.RETRY,
        coverage=CoverageMetricsDTOv2(
            clause_coverage=[],
            overall_coverage_score=score / 100,
            uncovered_clauses=[],
            coverage_method="token",
        ),
        strength=EvidenceStrengthDTO(
            strength_score=0.5,
            source_authority_score=0.7,
            corroboration_score=0.3,
            citation_density_score=0.5,
            rerank_confidence_score=0.5,
        ),
        freshness=FreshnessReportDTOv2(
            mean_freshness_score=1.0,
            per_chunk_freshness=[],
            oldest_document_days=0,
            freshest_document_days=0,
            decay_function_used="linear",
        ),
        conflict=ConflictReportDTOv2(
            conflict_score=0.0,
            conflict_pairs=[],
            has_severe_conflict=False,
        ),
        is_degraded=False,
    )


@pytest.mark.asyncio
async def test_monotonic_regression_triggers_abort():
    controller = RetryController()
    qid = "q_mono_test"

    # First call: score=70 -> recorded in history
    ctx1 = RetryContextDTO(
        query_id=qid, tenant_id="t1", attempt_number=1,
        reason=RetryReason.LOW_CONFIDENCE,
        last_confidence=make_confidence(70.0),
    )
    d1 = await controller.handle_retry(ctx1)
    assert d1.action != RetryAction.ABORT   # First call, no prior history

    # Second call: score=60 (worse) -> ABORT
    ctx2 = RetryContextDTO(
        query_id=qid, tenant_id="t1", attempt_number=2,
        reason=RetryReason.LOW_CONFIDENCE,
        last_confidence=make_confidence(60.0),
    )
    d2 = await controller.handle_retry(ctx2)
    assert d2.action == RetryAction.ABORT
    assert d2.is_monotonic_regression is True


@pytest.mark.asyncio
async def test_monotonic_improvement_continues():
    controller = RetryController()
    qid = "q_improve_test"

    ctx1 = RetryContextDTO(
        query_id=qid, tenant_id="t1", attempt_number=1,
        reason=RetryReason.LOW_CONFIDENCE,
        last_confidence=make_confidence(55.0),
    )
    await controller.handle_retry(ctx1)

    ctx2 = RetryContextDTO(
        query_id=qid, tenant_id="t1", attempt_number=2,
        reason=RetryReason.LOW_CONFIDENCE,
        last_confidence=make_confidence(70.0),  # improved
    )
    d2 = await controller.handle_retry(ctx2)
    # Should NOT abort due to monotonic regression
    assert d2.is_monotonic_regression is False
'''
write_file("tests/unit/backend/modules/retry/test_retry_controller.py", test_controller)

print("impl_m7_tests.py completed.")
