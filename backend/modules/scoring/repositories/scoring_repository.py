from sqlalchemy.ext.asyncio import AsyncSession
from backend.modules.scoring.models.scoring_log import ScoringLogORM
from backend.modules.scoring.schemas.scoring_dto import ReliabilityScoreDTOv2

class ScoringRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_log(self, result: ReliabilityScoreDTOv2) -> ScoringLogORM:
        log_entry = ScoringLogORM(
            correlation_id=result.correlation_id,
            tenant_id=result.tenant_id,
            final_score=result.final_score,
            is_trusted=result.is_trusted,
            metadata_payload={
                "base_score": result.base_score,
                "penalty_deduction": result.penalty_deduction,
                "breakdown": result.breakdown
            }
        )
        self.session.add(log_entry)
        await self.session.commit()
        await self.session.refresh(log_entry)
        return log_entry
