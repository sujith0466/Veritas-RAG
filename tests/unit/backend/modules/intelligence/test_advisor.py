import pytest
from backend.modules.intelligence.services.advisor import IndexAdvisor

def test_index_advisor():
    advisor = IndexAdvisor()
    actions = advisor.analyze_index_health("t1", avg_latency_ms=600)
    assert len(actions) == 1
    assert "Re-cluster" in actions[0]
