from backend.modules.evaluation.repositories.evaluation_repository import EvaluationRepository
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
