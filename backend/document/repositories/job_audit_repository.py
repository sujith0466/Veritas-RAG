"""Processing job audit log persistence repository (`JobAuditRepository`).

Append-only audit trail for all job lifecycle events.
"""

from datetime import UTC, datetime
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.document.models.job_audit import ProcessingJobAuditLog


class JobAuditRepository:
    """Repository for append-only operations on ProcessingJobAuditLog entities."""

    async def append(
        self,
        job_id: uuid.UUID,
        event: str,
        actor: str,
        payload: dict[str, Any] | None,
        session: AsyncSession,
    ) -> ProcessingJobAuditLog:
        """Append a new audit log entry."""
        audit = ProcessingJobAuditLog(
            job_id=job_id,
            event=event,
            actor=actor,
            payload=payload,
            timestamp=datetime.now(UTC),
        )
        session.add(audit)
        await session.flush()
        await session.refresh(audit)
        return audit

    async def list_for_job(
        self, job_id: uuid.UUID, session: AsyncSession
    ) -> list[ProcessingJobAuditLog]:
        """Get all audit logs for a job in chronological order."""
        stmt = select(ProcessingJobAuditLog).where(
            ProcessingJobAuditLog.job_id == job_id,
            ProcessingJobAuditLog.is_deleted.is_(False),
        ).order_by(ProcessingJobAuditLog.timestamp.asc())
        result = await session.execute(stmt)
        return list(result.scalars().all())
