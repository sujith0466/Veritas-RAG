from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.modules.reflection.models.reflection_log import ReflectionLogORM
from backend.modules.reflection.schemas.reflection_dto import ReflectionResultDTOv2

class ReflectionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_log(self, result: ReflectionResultDTOv2) -> ReflectionLogORM:
        log_entry = ReflectionLogORM(
            correlation_id=result.correlation_id,
            tenant_id=result.tenant_id,
            overall_verdict=result.overall_verdict,
            hallucination_score=result.scores.hallucination_score,
            completeness_score=result.scores.completeness_score,
            consistency_score=result.scores.consistency_score,
            is_safe_to_serve=result.is_safe_to_serve,
            attempt_number=result.attempt_number,
            metadata_payload={
                "claim_results": [c.model_dump(mode="json") for c in result.claim_results],
                "completeness_report": result.completeness_report.model_dump(mode="json"),
                "logical_report": result.logical_report.model_dump(mode="json")
            }
        )
        self.session.add(log_entry)
        await self.session.commit()
        await self.session.refresh(log_entry)
        return log_entry

    async def get_logs_by_correlation(self, correlation_id: str, tenant_id: str) -> list[ReflectionLogORM]:
        result = await self.session.execute(
            select(ReflectionLogORM)
            .where(ReflectionLogORM.correlation_id == correlation_id)
            .where(ReflectionLogORM.tenant_id == tenant_id)
            .order_by(ReflectionLogORM.attempt_number.asc())
        )
        return list(result.scalars().all())
