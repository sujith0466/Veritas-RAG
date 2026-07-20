import pytest
import pytest_asyncio
from backend.modules.reflection.services.completeness_evaluator import CompletenessEvaluator

@pytest.mark.asyncio
async def test_completeness_perfect_match():
    evaluator = CompletenessEvaluator()
    query = "What is the capital of France and what is the population?"
    answer = "The capital of France is Paris and its population is 2 million."
    
    score, unaddressed = await evaluator.evaluate(query, answer)
    assert score == 1.0
    assert len(unaddressed) == 0

@pytest.mark.asyncio
async def test_completeness_partial_match():
    evaluator = CompletenessEvaluator()
    query = "What is the capital of France and what is the population?"
    answer = "The capital of France is Paris."
    
    score, unaddressed = await evaluator.evaluate(query, answer)
    assert score == 0.5
    assert len(unaddressed) == 1
    assert "population" in unaddressed[0]
