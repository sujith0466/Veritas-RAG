import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

# ---------------------------------------------------------------------------
# Milestone 15.3: Orchestration & APIs
# ---------------------------------------------------------------------------

def main():
    print("Starting Milestone 15.3 Implementation...")

    # 1. continuous_learning.py
    learning_path = "backend/modules/evaluation/services/continuous_learning.py"
    if not os.path.exists(learning_path):
        with open(learning_path, "w") as f:
            f.write("""from backend.modules.evaluation.repositories.evaluation_repository import EvaluationRepository
from backend.modules.evaluation.services.dataset_manager import GoldenDatasetManager
from backend.modules.evaluation.services.batch_evaluator import BatchEvaluator
from backend.modules.evaluation.schemas.evaluation_dto import EvaluationResultDTO

class ContinuousLearningEngine:
    def __init__(
        self,
        repository: EvaluationRepository,
        dataset_manager: GoldenDatasetManager,
        batch_evaluator: BatchEvaluator
    ):
        self.repository = repository
        self.dataset_manager = dataset_manager
        self.batch_evaluator = batch_evaluator

    async def run_evaluation(self, dataset_id: str, system_outputs: list[dict]) -> EvaluationResultDTO:
        \"\"\"
        Orchestrates an evaluation run on a dataset using pre-computed system outputs.
        (In a full E2E run, it would trigger the RAG pipeline for each query).
        \"\"\"
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
            total_examples=metrics["total"]
        )
        
        await self.repository.save_evaluation_run(result)
        
        return result
""")
        print("Created continuous_learning.py")

    # 2. api/routes.py
    with open("backend/modules/evaluation/api/__init__.py", "w") as f:
        f.write('"""Evaluation API routes."""\n')

    routes_path = "backend/modules/evaluation/api/routes.py"
    if not os.path.exists(routes_path):
        with open(routes_path, "w") as f:
            f.write("""from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.engine import get_db_session
from backend.modules.evaluation.schemas.evaluation_dto import DatasetCreateDTO, EvaluationResultDTO
from backend.modules.evaluation.services.continuous_learning import ContinuousLearningEngine
from backend.modules.evaluation.services.dataset_manager import GoldenDatasetManager
from backend.modules.evaluation.services.batch_evaluator import BatchEvaluator
from backend.modules.evaluation.services.metric_calculator import MetricCalculator
from backend.modules.evaluation.repositories.evaluation_repository import EvaluationRepository
from pydantic import BaseModel

router = APIRouter(prefix="/evaluation/v1", tags=["Evaluation"])

class EvaluationRequestDTO(BaseModel):
    dataset_id: str
    system_outputs: list[dict]

def get_learning_engine(session: AsyncSession = Depends(get_db_session)) -> ContinuousLearningEngine:
    repo = EvaluationRepository(session)
    dataset_manager = GoldenDatasetManager(repo)
    metric_calc = MetricCalculator()
    batch_evaluator = BatchEvaluator(metric_calc)
    return ContinuousLearningEngine(repo, dataset_manager, batch_evaluator)

def get_dataset_manager(session: AsyncSession = Depends(get_db_session)) -> GoldenDatasetManager:
    repo = EvaluationRepository(session)
    return GoldenDatasetManager(repo)

@router.post("/datasets", response_model=str)
async def create_dataset(
    request: DatasetCreateDTO,
    manager: GoldenDatasetManager = Depends(get_dataset_manager)
):
    try:
        return await manager.create_dataset(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/run", response_model=EvaluationResultDTO)
async def run_evaluation(
    request: EvaluationRequestDTO,
    engine: ContinuousLearningEngine = Depends(get_learning_engine)
):
    try:
        return await engine.run_evaluation(request.dataset_id, request.system_outputs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
""")
        print("Created api/routes.py")

    print("Milestone 15.3 completed.")

if __name__ == "__main__":
    main()
