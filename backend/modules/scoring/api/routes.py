from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.engine import get_db_session
from backend.modules.scoring.repositories.scoring_repository import \
    ScoringRepository
from backend.modules.scoring.schemas.scoring_dto import (ReliabilityScoreDTOv2,
                                                         ScoringRequestDTO)
from backend.modules.scoring.services.scoring_engine import ScoringEngine

router = APIRouter(prefix="/scoring/v1", tags=["Scoring"])


def get_scoring_engine(
    session: AsyncSession = Depends(get_db_session),
) -> ScoringEngine:
    repo = ScoringRepository(session)
    return ScoringEngine(repo)


@router.post("/calculate", response_model=ReliabilityScoreDTOv2)
async def calculate_reliability_score(
    request: ScoringRequestDTO, engine: ScoringEngine = Depends(get_scoring_engine)
):
    try:
        return await engine.calculate_score(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
