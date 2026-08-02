from backend.modules.intelligence.services.optimizer import ThresholdOptimizer


def test_threshold_optimizer():
    optimizer = ThresholdOptimizer()

    res1 = optimizer.analyze_thresholds("t1", historical_false_positives=50)
    assert res1 is None

    res2 = optimizer.analyze_thresholds("t1", historical_false_positives=150)
    assert res2 is not None
    assert res2.recommended_value == 0.75
