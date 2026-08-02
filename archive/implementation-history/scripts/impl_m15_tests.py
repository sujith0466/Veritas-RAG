import os
import subprocess
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

# ---------------------------------------------------------------------------
# Milestone 15.4: Unit Tests & Verification
# ---------------------------------------------------------------------------

def main():
    print("Starting Milestone 15.4 Implementation (Tests)...")
    os.makedirs("tests/unit/backend/modules/evaluation", exist_ok=True)

    # 1. test_metric_calculator.py
    t_metrics_path = "tests/unit/backend/modules/evaluation/test_metric_calculator.py"
    with open(t_metrics_path, "w") as f:
        f.write("""import pytest
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
""")

    # 2. test_batch_evaluator.py
    t_batch_path = "tests/unit/backend/modules/evaluation/test_batch_evaluator.py"
    with open(t_batch_path, "w") as f:
        f.write("""import pytest
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
""")

    # 3. test_continuous_learning.py
    t_learning_path = "tests/unit/backend/modules/evaluation/test_continuous_learning.py"
    with open(t_learning_path, "w") as f:
        f.write("""import pytest
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
""")

    print("Created test files.")

    print("Running tests...")
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/unit/backend/modules/evaluation"], capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        sys.exit(1)

    print("Milestone 15.4 completed.")

if __name__ == "__main__":
    main()
