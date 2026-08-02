import os
import subprocess
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

def main():
    print("Starting Milestone 19.4 Implementation (Tests)...")
    os.makedirs("tests/unit/backend/modules/analytics", exist_ok=True)
    os.makedirs("tests/integration", exist_ok=True)

    # 1. test_pricing.py
    with open("tests/unit/backend/modules/analytics/test_pricing.py", "w") as f:
        f.write("""import pytest
from backend.modules.analytics.services.pricing import PricingEngine
from backend.modules.analytics.schemas.errors import InvalidPricingModelError

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
""")

    # 2. test_quota.py
    with open("tests/unit/backend/modules/analytics/test_quota.py", "w") as f:
        f.write("""import pytest
from backend.modules.analytics.services.quota import QuotaGovernor
from backend.modules.analytics.schemas.errors import QuotaExceededError

@pytest.mark.asyncio
async def test_quota_governor():
    gov = QuotaGovernor()
    # t1 starts with 100,000 mock quota
    
    assert await gov.check_and_reserve("t1", 50000) is True
    assert gov._mock_redis["quota:tokens:t1"] == 50000
    
    with pytest.raises(QuotaExceededError):
        await gov.check_and_reserve("t1", 60000)
        
    await gov.adjust_reservation_diff("t1", 10000)
    assert gov._mock_redis["quota:tokens:t1"] == 60000
""")

    # 3. test_roi.py
    with open("tests/unit/backend/modules/analytics/test_roi.py", "w") as f:
        f.write("""import pytest
from backend.modules.analytics.services.roi import ROIAttributionEngine
from backend.modules.analytics.services.forecaster import TrendForecaster

def test_roi_engine():
    engine = ROIAttributionEngine(ticket_cost_usd=10.0, incident_cost_usd=100.0)
    roi = engine.calculate_roi("t1", queries_trusted=100, hallucinations_blocked=5, total_llm_cost_usd=20.0)
    
    # 100 * 10 = 1000
    # 5 * 100 = 500
    # 1000 + 500 - 20 = 1480
    assert roi.ticket_savings_usd == 1000.0
    assert roi.incident_savings_usd == 500.0
    assert roi.net_roi_usd == 1480.0

def test_forecaster():
    forecaster = TrendForecaster()
    forecast = forecaster.forecast_90_days("t1", historical_cost_per_day=5.0, historical_tokens_per_day=1000.0)
    
    assert forecast.projected_cost_90d_usd == 450.0
    assert forecast.projected_tokens_90d == 90000
""")

    print("Created test files.")

    print("Running tests...")
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/unit/backend/modules/analytics/test_pricing.py", "tests/unit/backend/modules/analytics/test_quota.py", "tests/unit/backend/modules/analytics/test_roi.py"], capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        sys.exit(1)

    print("Milestone 19.4 completed.")

if __name__ == "__main__":
    main()
