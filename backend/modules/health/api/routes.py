from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.engine import get_db_session
from backend.modules.health.schemas.health_dto import HealthReportDTO
from backend.modules.health.tasks.health_tasks import HealthAnalysisTask
from backend.modules.health.repositories.health_repository import HealthRepository
from pydantic import BaseModel

router = APIRouter(prefix="/health/v1", tags=["KnowledgeHealth"])

class AnalysisRequestDTO(BaseModel):
    tenant_id: str
    documents: list[dict]  # Simplified for M14

def get_health_task(session: AsyncSession = Depends(get_db_session)) -> HealthAnalysisTask:
    repo = HealthRepository(session)
    return HealthAnalysisTask(repo)

@router.post("/analyze", response_model=HealthReportDTO)
async def analyze_corpus(
    request: AnalysisRequestDTO,
    task: HealthAnalysisTask = Depends(get_health_task)
):
    try:
        # In a real system this would be a celery task, but we await it here for M14 tests
        return await task.run_analysis(request.tenant_id, request.documents)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
