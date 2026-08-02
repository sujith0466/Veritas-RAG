import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

# ---------------------------------------------------------------------------
# Milestone 15.2: Evaluators & Metrics
# ---------------------------------------------------------------------------

def main():
    print("Starting Milestone 15.2 Implementation...")

    # 1. dataset_manager.py
    manager_path = "backend/modules/evaluation/services/dataset_manager.py"
    if not os.path.exists(manager_path):
        with open(manager_path, "w") as f:
            f.write("""from backend.modules.evaluation.repositories.evaluation_repository import EvaluationRepository
from backend.modules.evaluation.schemas.evaluation_dto import DatasetCreateDTO
from backend.modules.evaluation.schemas.errors import EvaluationDomainException, EvaluationErrorCode

class GoldenDatasetManager:
    def __init__(self, repository: EvaluationRepository):
        self.repository = repository

    async def create_dataset(self, dto: DatasetCreateDTO) -> str:
        dataset = await self.repository.create_dataset(dto)
        return str(dataset.id)

    async def get_dataset_examples(self, dataset_id: str) -> list[dict]:
        dataset = await self.repository.get_dataset(dataset_id)
        if not dataset:
            raise EvaluationDomainException(f"Dataset {dataset_id} not found", EvaluationErrorCode.DATASET_NOT_FOUND)
        return dataset.examples
""")
        print("Created dataset_manager.py")

    # 2. metric_calculator.py
    metrics_path = "backend/modules/evaluation/services/metric_calculator.py"
    if not os.path.exists(metrics_path):
        with open(metrics_path, "w") as f:
            f.write("""import re

class MetricCalculator:
    def calculate_retrieval_metrics(self, expected_ids: list[str], retrieved_ids: list[str]) -> tuple[float, float, float]:
        \"\"\"
        Calculates Precision, Recall, and F1 score for document retrieval.
        \"\"\"
        if not expected_ids and not retrieved_ids:
            return 1.0, 1.0, 1.0
        if not expected_ids or not retrieved_ids:
            return 0.0, 0.0, 0.0
            
        expected_set = set(expected_ids)
        retrieved_set = set(retrieved_ids)
        
        true_positives = len(expected_set.intersection(retrieved_set))
        
        precision = true_positives / len(retrieved_set) if retrieved_set else 0.0
        recall = true_positives / len(expected_set) if expected_set else 0.0
        
        if precision + recall == 0:
            f1 = 0.0
        else:
            f1 = 2 * (precision * recall) / (precision + recall)
            
        return precision, recall, f1

    def calculate_answer_similarity(self, expected_answer: str, actual_answer: str) -> float:
        \"\"\"
        Simple token overlap for exact answer match estimation.
        \"\"\"
        words1 = set(re.findall(r'\\w+', expected_answer.lower()))
        words2 = set(re.findall(r'\\w+', actual_answer.lower()))
        if not words1 or not words2:
            return 0.0
        return len(words1.intersection(words2)) / max(len(words1), len(words2))
""")
        print("Created metric_calculator.py")

    # 3. batch_evaluator.py
    batch_path = "backend/modules/evaluation/services/batch_evaluator.py"
    if not os.path.exists(batch_path):
        with open(batch_path, "w") as f:
            f.write("""from backend.modules.evaluation.services.metric_calculator import MetricCalculator

class BatchEvaluator:
    def __init__(self, metric_calculator: MetricCalculator):
        self.metric_calculator = metric_calculator

    async def evaluate_batch(self, examples: list[dict], system_outputs: list[dict]) -> dict:
        \"\"\"
        Aggregates metrics across a batch of examples.
        \"\"\"
        total_p = 0.0
        total_r = 0.0
        total_f1 = 0.0
        total_rel = 0.0
        
        n = len(examples)
        if n == 0:
            return {"precision": 0.0, "recall": 0.0, "f1_score": 0.0, "average_reliability_score": 0.0, "total": 0}
            
        for i in range(n):
            expected = examples[i].get("expected_document_ids", [])
            output = system_outputs[i]
            retrieved = output.get("retrieved_document_ids", [])
            reliability = output.get("reliability_score", 0.0)
            
            p, r, f1 = self.metric_calculator.calculate_retrieval_metrics(expected, retrieved)
            
            total_p += p
            total_r += r
            total_f1 += f1
            total_rel += reliability
            
        return {
            "precision": total_p / n,
            "recall": total_r / n,
            "f1_score": total_f1 / n,
            "average_reliability_score": total_rel / n,
            "total": n
        }
""")
        print("Created batch_evaluator.py")

    print("Milestone 15.2 completed.")

if __name__ == "__main__":
    main()
