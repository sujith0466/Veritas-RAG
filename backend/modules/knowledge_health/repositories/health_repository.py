"""Repository implementation for Knowledge Health audit logs and stale records (`ADR-005`)."""

from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
from sqlalchemy import desc, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from backend.modules.knowledge_health.models.health_scan import HealthScanJob
from backend.modules.knowledge_health.models.stale_record import StaleEmbeddingRecord


class HealthRepository:
    """Async repository managing health scan jobs and model drift tracking records."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def log_scan_job(self, job: HealthScanJob) -> UUID:
        """Persist a new health scan job record."""
        self.session.add(job)
        await self.session.flush()
        await self.session.refresh(job)
        return job.id

    async def update_scan_progress(
        self,
        job_id: UUID,
        status: str,
        stats: Optional[Dict[str, Any]] = None,
    ) -> Optional[HealthScanJob]:
        """Update job status and cumulative metrics."""
        stmt = select(HealthScanJob).where(HealthScanJob.id == job_id)
        result = await self.session.execute(stmt)
        job = result.scalar_one_or_none()
        if not job:
            return None

        job.status = status
        if stats:
            if "orphans_found" in stats:
                job.orphans_found = int(stats["orphans_found"])
            if "orphans_purged" in stats:
                job.orphans_purged = int(stats["orphans_purged"])
            if "stale_chunks_found" in stats:
                job.stale_chunks_found = int(stats["stale_chunks_found"])
            if "parity_status" in stats:
                job.parity_status = str(stats["parity_status"])
            if "duration_ms" in stats:
                job.duration_ms = float(stats["duration_ms"])
            if "error_message" in stats:
                job.error_message = stats["error_message"]

        await self.session.flush()
        await self.session.refresh(job)
        return job

    async def get_scan_job(self, job_id: UUID, tenant_id: str) -> Optional[HealthScanJob]:
        """Fetch a specific scan job by ID and tenant namespace."""
        stmt = select(HealthScanJob).where(
            HealthScanJob.id == job_id,
            HealthScanJob.tenant_id == tenant_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_scan_jobs(
        self,
        tenant_id: str,
        scan_type: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> Tuple[List[HealthScanJob], int]:
        """Paginated query of past health scan jobs for a tenant."""
        query = select(HealthScanJob).where(HealthScanJob.tenant_id == tenant_id)
        count_query = select(func.count(HealthScanJob.id)).where(HealthScanJob.tenant_id == tenant_id)

        if scan_type and scan_type != "ALL":
            query = query.where(HealthScanJob.scan_type == scan_type)
            count_query = count_query.where(HealthScanJob.scan_type == scan_type)

        total_res = await self.session.execute(count_query)
        total_count = total_res.scalar_one_or_none() or 0

        query = query.order_by(desc(HealthScanJob.created_at)).offset((page - 1) * size).limit(size)
        items_res = await self.session.execute(query)
        items = list(items_res.scalars().all())

        return items, total_count

    async def create_stale_record(self, record: StaleEmbeddingRecord) -> UUID:
        """Persist a stale embedding tracking record."""
        self.session.add(record)
        await self.session.flush()
        await self.session.refresh(record)
        return record.id

    async def get_stale_records(
        self,
        tenant_id: str,
        status: str = "PENDING",
    ) -> List[StaleEmbeddingRecord]:
        """Retrieve all pending stale embedding records for a tenant."""
        stmt = (
            select(StaleEmbeddingRecord)
            .where(
                StaleEmbeddingRecord.tenant_id == tenant_id,
                StaleEmbeddingRecord.status == status,
            )
            .order_by(StaleEmbeddingRecord.created_at)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_stale_record_status(self, record_id: UUID, status: str) -> bool:
        """Update the processing status of a stale embedding record."""
        stmt = select(StaleEmbeddingRecord).where(StaleEmbeddingRecord.id == record_id)
        result = await self.session.execute(stmt)
        record = result.scalar_one_or_none()
        if not record:
            return False
        record.status = status
        await self.session.flush()
        return True
