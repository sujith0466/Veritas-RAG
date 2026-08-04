"""Failed Job Diagnostics Repository (`FailedJobRepository`).

Provides persistence operations for DLQ forensic failure diagnostics and triage status.
"""

from datetime import UTC, datetime
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.document.models.failed_job import FailedJobDiagnostics


class FailedJobRepository:
    """Repository for managing FailedJobDiagnostics records."""

    async def create_diagnostics(
        self, diagnostics: FailedJobDiagnostics, session: AsyncSession
    ) -> FailedJobDiagnostics:
        """Persist a new forensic failure diagnostic record."""
        session.add(diagnostics)
        await session.flush()
        await session.refresh(diagnostics)
        return diagnostics

    async def get_by_job_id(
        self, job_id: uuid.UUID, session: AsyncSession
    ) -> FailedJobDiagnostics | None:
        """Fetch diagnostic details for a specific processing job."""
        stmt = (
            select(FailedJobDiagnostics)
            .where(
                FailedJobDiagnostics.job_id == job_id,
                FailedJobDiagnostics.is_deleted.is_(False),
            )
            .order_by(FailedJobDiagnostics.created_at.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_remediation_status(
        self,
        job_id: uuid.UUID,
        status: str,
        user_id: uuid.UUID | None,
        session: AsyncSession,
    ) -> FailedJobDiagnostics | None:
        """Update remediation state (e.g. RESOLVED_REPLAY, DISMISSED_IGNORED)."""
        diag = await self.get_by_job_id(job_id, session)
        if diag:
            diag.remediation_status = status
            diag.resolved_by_user_id = user_id
            diag.resolved_at = datetime.now(UTC)
            await session.flush()
            await session.refresh(diag)
        return diag

    async def list_diagnostics(
        self,
        tenant_id: str,
        remediation_status: str | None,
        page: int,
        size: int,
        session: AsyncSession,
    ) -> list[FailedJobDiagnostics]:
        """List failed job diagnostics with tenant isolation and status filtering."""
        stmt = select(FailedJobDiagnostics).where(
            FailedJobDiagnostics.tenant_id == tenant_id,
            FailedJobDiagnostics.is_deleted.is_(False),
        )
        if remediation_status:
            stmt = stmt.where(FailedJobDiagnostics.remediation_status == remediation_status)

        stmt = (
            stmt.order_by(FailedJobDiagnostics.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def bulk_dismiss(
        self,
        job_ids: list[uuid.UUID],
        tenant_id: str,
        user_id: uuid.UUID | None,
        session: AsyncSession,
    ) -> int:
        """Bulk dismiss/ignore quarantined failed jobs."""
        if not job_ids:
            return 0
        stmt = (
            update(FailedJobDiagnostics)
            .where(
                FailedJobDiagnostics.job_id.in_(job_ids),
                FailedJobDiagnostics.tenant_id == tenant_id,
                FailedJobDiagnostics.is_deleted.is_(False),
            )
            .values(
                remediation_status="DISMISSED_IGNORED",
                resolved_by_user_id=user_id,
                resolved_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        result = await session.execute(stmt)
        return result.rowcount
