from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.health.models.health_log import HealthLogORM, QuarantineLogORM
from backend.modules.health.schemas.health_dto import HealthReportDTO, QuarantineRequestDTO


class HealthRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_health_report(self, report: HealthReportDTO) -> HealthLogORM:
        log_entry = HealthLogORM(
            tenant_id=report.tenant_id,
            health_score=report.health_score,
            issues_found_count=len(report.issues_found),
            metadata_payload={
                "total_documents_analyzed": report.total_documents_analyzed,
                "issues": [i.model_dump(mode="json") for i in report.issues_found],
                "quarantined": report.quarantined_documents,
            },
        )
        self.session.add(log_entry)
        await self.session.commit()
        await self.session.refresh(log_entry)
        return log_entry

    async def save_quarantine_action(
        self, request: QuarantineRequestDTO
    ) -> QuarantineLogORM:
        log_entry = QuarantineLogORM(
            document_id=request.document_id,
            action=request.action,
            reason=request.reason,
        )
        self.session.add(log_entry)
        await self.session.commit()
        await self.session.refresh(log_entry)
        return log_entry
