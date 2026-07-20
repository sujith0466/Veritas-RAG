import pytest
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
