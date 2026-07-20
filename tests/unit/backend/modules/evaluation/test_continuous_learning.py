import pytest
from unittest.mock import AsyncMock
from backend.modules.evaluation.services.continuous_learning import ContinuousLearningEngine

@pytest.mark.asyncio
async def test_continuous_learning_engine():
    mock_repo = AsyncMock()
    mock_dataset_manager = AsyncMock()
    mock_batch_evaluator = AsyncMock()
    
    mock_dataset_manager.get_dataset_examples.return_value = [{"query": "test"}]
    mock_batch_evaluator.evaluate_batch.return_value = {
        "precision": 1.0,
        "recall": 1.0,
        "f1_score": 1.0,
        "average_reliability_score": 95.0,
        "total": 1
    }
    
    engine = ContinuousLearningEngine(mock_repo, mock_dataset_manager, mock_batch_evaluator)
    
    result = await engine.run_evaluation("dataset-123", [{"output": "test"}])
    
    assert result.dataset_id == "dataset-123"
    assert result.precision == 1.0
    assert result.average_reliability_score == 95.0
    assert mock_repo.save_evaluation_run.called
