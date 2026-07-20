from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.modules.validation.models.validation_log import ValidationLogORM
from backend.modules.validation.schemas.validation_dto import ValidationResultDTO

class ValidationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_log(self, result: ValidationResultDTO) -> ValidationLogORM:
        log_entry = ValidationLogORM(
            correlation_id=result.correlation_id,
            tenant_id=result.tenant_id,
            overall_verdict=result.overall_verdict,
            entailment_ratio=result.entailment_ratio,
            unsupported_claim_count=result.unsupported_claim_count,
            invalid_citation_count=result.invalid_citation_count,
            is_valid=result.is_valid,
            metadata_payload={
                "claim_details": [c.model_dump(mode="json") for c in result.claim_details]
            }
        )
        self.session.add(log_entry)
        await self.session.commit()
        await self.session.refresh(log_entry)
        return log_entry
