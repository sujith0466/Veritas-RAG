"""Unit tests for RuleEngine — Phase 7."""

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


def test_rule_engine_timeout():
    engine = RuleEngine()
    rule = engine.evaluate(RetryReason.TIMEOUT)
    assert rule.action == RetryAction.RETRY_WITH_FALLBACK_MODEL


def test_rule_engine_malformed_output():
    engine = RuleEngine()
    rule = engine.evaluate(RetryReason.MALFORMED_OUTPUT)
    assert rule.action == RetryAction.RETRY_IMMEDIATE


def test_rule_engine_unknown_returns_abort():
    engine = RuleEngine()
    rule = engine.evaluate(RetryReason.UNKNOWN)
    assert rule.action == RetryAction.ABORT
    assert rule.base_backoff_ms == 0
