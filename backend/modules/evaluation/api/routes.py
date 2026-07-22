from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.engine import get_db_session
from backend.modules.evaluation.repositories.evaluation_repository import \
    EvaluationRepository
from backend.modules.evaluation.schemas.evaluation_dto import (
    DatasetCreateDTO, EvaluationResultDTO)
from backend.modules.evaluation.services.batch_evaluator import BatchEvaluator
from backend.modules.evaluation.services.continuous_learning import \
    ContinuousLearningEngine
from backend.modules.evaluation.services.dataset_manager import \
    GoldenDatasetManager
from backend.modules.evaluation.services.metric_calculator import \
    MetricCalculator

router = APIRouter(prefix="/evaluation/v1", tags=["Evaluation"])


class EvaluationRequestDTO(BaseModel):
    dataset_id: str
    system_outputs: list[dict]


def get_learning_engine(
    session: AsyncSession = Depends(get_db_session),
) -> ContinuousLearningEngine:
    repo = EvaluationRepository(session)
    dataset_manager = GoldenDatasetManager(repo)
    metric_calc = MetricCalculator()
    batch_evaluator = BatchEvaluator(metric_calc)
    return ContinuousLearningEngine(repo, dataset_manager, batch_evaluator)


def get_dataset_manager(
    session: AsyncSession = Depends(get_db_session),
) -> GoldenDatasetManager:
    repo = EvaluationRepository(session)
    return GoldenDatasetManager(repo)


@router.post("/datasets", response_model=str)
async def create_dataset(
    request: DatasetCreateDTO,
    manager: GoldenDatasetManager = Depends(get_dataset_manager),
):
    try:
        return await manager.create_dataset(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run", response_model=EvaluationResultDTO)
async def run_evaluation(
    request: EvaluationRequestDTO,
    engine: ContinuousLearningEngine = Depends(get_learning_engine),
):
    try:
        return await engine.run_evaluation(request.dataset_id, request.system_outputs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
