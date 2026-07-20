import pytest
from backend.modules.evaluation.services.batch_evaluator import BatchEvaluator
from backend.modules.evaluation.services.metric_calculator import MetricCalculator

@pytest.mark.asyncio
async def test_evaluate_batch():
    evaluator = BatchEvaluator(MetricCalculator())
    
    examples = [
        {"expected_document_ids": ["doc1"]},
        {"expected_document_ids": ["doc2", "doc3"]}
    ]
    
    system_outputs = [
        {"retrieved_document_ids": ["doc1"], "reliability_score": 90.0},
        {"retrieved_document_ids": ["doc2", "doc4"], "reliability_score": 80.0}
    ]
    
    metrics = await evaluator.evaluate_batch(examples, system_outputs)
    
    assert metrics["total"] == 2
    assert metrics["precision"] == 0.75  # (1.0 + 0.5) / 2
    assert metrics["recall"] == 0.75     # (1.0 + 0.5) / 2
    assert metrics["f1_score"] == 0.75
    assert metrics["average_reliability_score"] == 85.0
