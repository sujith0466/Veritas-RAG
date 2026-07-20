from backend.modules.evaluation.services.metric_calculator import MetricCalculator

class BatchEvaluator:
    def __init__(self, metric_calculator: MetricCalculator):
        self.metric_calculator = metric_calculator

    async def evaluate_batch(self, examples: list[dict], system_outputs: list[dict]) -> dict:
        """
        Aggregates metrics across a batch of examples.
        """
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
