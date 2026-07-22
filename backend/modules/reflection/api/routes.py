from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.engine import get_db_session
from backend.modules.reflection.repositories.reflection_repository import \
    ReflectionRepository
from backend.modules.reflection.schemas.reflection_dto import (
    ReflectionRequestDTOv2, ReflectionResultDTOv2)
from backend.modules.reflection.services.reflection_engine import \
    ReflectionEngineV2

router = APIRouter(prefix="/reflection/v2", tags=["Reflection"])


def get_reflection_engine(
    session: AsyncSession = Depends(get_db_session),
) -> ReflectionEngineV2:
    repo = ReflectionRepository(session)
    return ReflectionEngineV2(repo)


@router.post("/evaluate", response_model=ReflectionResultDTOv2)
async def evaluate_reflection(
    request: ReflectionRequestDTOv2,
    engine: ReflectionEngineV2 = Depends(get_reflection_engine),
):
    try:
        return await engine.reflect_async(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{correlation_id}", response_model=list[ReflectionResultDTOv2])
async def get_reflection_history(
    correlation_id: str, tenant_id: str, session: AsyncSession = Depends(get_db_session)
):
    repo = ReflectionRepository(session)
    logs = await repo.get_logs_by_correlation(correlation_id, tenant_id)
    return [
        ReflectionResultDTOv2(
            correlation_id=log.correlation_id,
            tenant_id=log.tenant_id,
            overall_verdict=log.overall_verdict,
            scores={
                "hallucination_score": log.hallucination_score,
                "completeness_score": log.completeness_score,
                "consistency_score": log.consistency_score,
            },
            claim_results=log.metadata_payload.get("claim_results", []),
            completeness_report=log.metadata_payload.get("completeness_report", {}),
            logical_report=log.metadata_payload.get("logical_report", {}),
            is_safe_to_serve=log.is_safe_to_serve,
            attempt_number=log.attempt_number,
        )
        for log in logs
    ]
