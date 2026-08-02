import pytest

from backend.modules.analytics.schemas.errors import InvalidPricingModelError
from backend.modules.analytics.services.pricing import PricingEngine


def test_pricing_engine():
    engine = PricingEngine()

    # gpt-4o: prompt 0.000005, completion 0.000015
    # 1000 * 0.000005 = 0.005
    # 500 * 0.000015 = 0.0075
    # Total: 0.0125
    cost = engine.compute_cost("openai", "gpt-4o", 1000, 500)
    assert abs(cost - 0.0125) < 1e-9

    with pytest.raises(InvalidPricingModelError):
        engine.compute_cost("unknown", "unknown-model", 100, 100)
