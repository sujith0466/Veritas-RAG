"""Unit tests for WP-3B ModelPricingService dynamic financial rate calculation."""

import pytest

from backend.modules.analytics.schemas.errors import InvalidPricingModelError
from backend.modules.analytics.services.pricing import (
    CostCalculationResult,
    ModelPricingService,
    PricingEngine,
)


def test_model_pricing_service_known_models():
    service = ModelPricingService()

    # gpt-4o: prompt $5.00/1M ($0.000005/tok), comp $15.00/1M ($0.000015/tok)
    # 1,000 prompt tokens + 500 comp tokens = 0.005 + 0.0075 = $0.0125
    res = service.calculate_cost("openai", "gpt-4o", 1000, 500)
    assert res.cost_status == "PRICED"
    assert res.is_zero_cost is False
    assert abs(res.total_cost_usd - 0.0125) < 1e-8
    assert res.prompt_rate_per_1m == 5.00
    assert res.completion_rate_per_1m == 15.00

    # gpt-4o-mini: prompt $0.15/1M, comp $0.60/1M
    # 10,000 prompt tokens + 2,000 comp tokens = 0.0015 + 0.0012 = $0.0027
    res_mini = service.calculate_cost("openai", "gpt-4o-mini", 10000, 2000)
    assert res_mini.cost_status == "PRICED"
    assert abs(res_mini.total_cost_usd - 0.0027) < 1e-8

    # claude-3-5-sonnet: prompt $3.00/1M, comp $15.00/1M
    res_claude = service.calculate_cost("anthropic", "claude-3-5-sonnet", 5000, 1000)
    assert res_claude.cost_status == "PRICED"
    assert abs(res_claude.total_cost_usd - 0.030) < 1e-8

    # gemini-1.5-flash: prompt $0.35/1M, comp $1.05/1M
    res_flash = service.calculate_cost("google", "gemini-1.5-flash", 100000, 20000)
    assert res_flash.cost_status == "PRICED"
    assert abs(res_flash.total_cost_usd - (0.035 + 0.021)) < 1e-8


def test_model_pricing_service_legitimate_zero_cost_models():
    service = ModelPricingService()

    # Local embedding model or test zero-cost model
    res_local = service.calculate_cost("local", "all-minilm-l6-v2", 50000, 0)
    assert res_local.cost_status == "PRICED"
    assert res_local.is_zero_cost is True
    assert res_local.total_cost_usd == 0.0

    res_mock = service.calculate_cost("test", "mock-llm", 1000, 500)
    assert res_mock.cost_status == "PRICED"
    assert res_mock.is_zero_cost is True
    assert res_mock.total_cost_usd == 0.0


def test_model_pricing_service_unknown_or_unsupported_models():
    """Requirement: Unknown or unconfigured models must explicitly be UNPRICED."""
    service = ModelPricingService()

    res_unknown = service.calculate_cost("custom-provider", "unknown-enterprise-llm", 1000, 500)
    assert res_unknown.cost_status == "UNPRICED"
    assert res_unknown.is_zero_cost is False
    assert res_unknown.prompt_rate_per_1m is None

    res_empty = service.calculate_cost(None, "", 100, 100)
    assert res_empty.cost_status == "UNPRICED"


def test_model_pricing_service_zero_tokens():
    service = ModelPricingService()

    res = service.calculate_cost("openai", "gpt-4o", 0, 0)
    assert res.cost_status == "PRICED"
    assert res.total_cost_usd == 0.0


def test_pricing_engine_compatibility_facade():
    engine = PricingEngine()

    cost = engine.compute_cost("openai", "gpt-4o", 1000, 500)
    assert abs(cost - 0.0125) < 1e-8

    with pytest.raises(InvalidPricingModelError):
        engine.compute_cost("unknown", "unknown-model", 100, 100)
