from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.modules.evaluation.models.evaluation_log import GoldenDatasetORM, EvaluationRunORM
from backend.modules.evaluation.schemas.evaluation_dto import DatasetCreateDTO, EvaluationResultDTO
import uuid

class EvaluationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_dataset(self, dto: DatasetCreateDTO) -> GoldenDatasetORM:
        dataset = GoldenDatasetORM(
            tenant_id=dto.tenant_id,
            name=dto.name,
            examples=[e.model_dump(mode="json") for e in dto.examples]
        )
        self.session.add(dataset)
        await self.session.commit()
        await self.session.refresh(dataset)
        return dataset

    async def get_dataset(self, dataset_id: str) -> GoldenDatasetORM | None:
        stmt = select(GoldenDatasetORM).where(GoldenDatasetORM.id == uuid.UUID(dataset_id))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def save_evaluation_run(self, result: EvaluationResultDTO) -> EvaluationRunORM:
        run = EvaluationRunORM(
            dataset_id=uuid.UUID(result.dataset_id),
            precision=result.precision,
            recall=result.recall,
            f1_score=result.f1_score,
            average_reliability_score=result.average_reliability_score,
            total_examples=result.total_examples
        )
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run
