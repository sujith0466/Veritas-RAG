from backend.modules.evaluation.services.metric_calculator import MetricCalculator


def test_calculate_retrieval_metrics():
    calc = MetricCalculator()

    p, r, f1 = calc.calculate_retrieval_metrics(["doc1", "doc2"], ["doc1", "doc3"])

    assert p == 0.5
    assert r == 0.5
    assert f1 == 0.5

def test_calculate_answer_similarity():
    calc = MetricCalculator()

    sim = calc.calculate_answer_similarity("The quick brown fox", "the quick brown FOX")
    assert sim == 1.0

    sim2 = calc.calculate_answer_similarity("The quick brown fox", "A completely different answer")
    assert sim2 == 0.0
