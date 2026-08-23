from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.engine import get_async_session
from backend.modules.validation.providers.cross_encoder_provider import (
    HeuristicNLIProvider,
    LocalCrossEncoderNLIProvider,
)
from backend.modules.validation.repositories.validation_repository import ValidationRepository
from backend.modules.validation.schemas.validation_dto import (
    ValidationRequestDTO,
    ValidationResultDTO,
)
from backend.modules.validation.services.nli_engine import NLIValidationEngine
from backend.modules.validation.services.validation_engine import ValidationEngine

router = APIRouter(prefix="/validation/v1", tags=["Validation"])

_nli_provider_instance = LocalCrossEncoderNLIProvider()


def get_validation_engine(
    session: AsyncSession = Depends(get_async_session),
) -> ValidationEngine:
    repo = ValidationRepository(session)
    nli = NLIValidationEngine(_nli_provider_instance)
    return ValidationEngine(repo, nli)


@router.post("/verify", response_model=ValidationResultDTO)
async def verify_answer(
    request: ValidationRequestDTO,
    engine: ValidationEngine = Depends(get_validation_engine),
):
    try:
        return await engine.validate(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
