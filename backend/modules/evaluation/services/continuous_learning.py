from backend.modules.evaluation.repositories.evaluation_repository import EvaluationRepository
from backend.modules.evaluation.schemas.evaluation_dto import EvaluationResultDTO
from backend.modules.evaluation.services.batch_evaluator import BatchEvaluator
from backend.modules.evaluation.services.dataset_manager import GoldenDatasetManager


class ContinuousLearningEngine:
    def __init__(
        self,
        repository: EvaluationRepository,
        dataset_manager: GoldenDatasetManager,
        batch_evaluator: BatchEvaluator,
    ):
        self.repository = repository
        self.dataset_manager = dataset_manager
        self.batch_evaluator = batch_evaluator

    async def run_evaluation(
        self, dataset_id: str, system_outputs: list[dict]
    ) -> EvaluationResultDTO:
        """
        Orchestrates an evaluation run on a dataset using pre-computed system outputs.
        (In a full E2E run, it would trigger the RAG pipeline for each query).
        """
        examples = await self.dataset_manager.get_dataset_examples(dataset_id)

        # In a real system, we might ensure len(examples) == len(system_outputs).
        # For M15, we assume they are zipped correctly.

        metrics = await self.batch_evaluator.evaluate_batch(examples, system_outputs)

        result = EvaluationResultDTO(
            dataset_id=dataset_id,
            precision=metrics["precision"],
            recall=metrics["recall"],
            f1_score=metrics["f1_score"],
            average_reliability_score=metrics["average_reliability_score"],
            total_examples=metrics["total"],
        )

        await self.repository.save_evaluation_run(result)

        return result
