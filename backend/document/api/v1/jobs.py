import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.dependencies.rbac import require_role
from backend.database.engine import get_async_session
from backend.document.repositories.failed_job_repository import FailedJobRepository
from backend.document.repositories.job_audit_repository import JobAuditRepository
from backend.document.repositories.job_repository import JobRepository
from backend.document.repositories.job_step_repository import JobStepRepository
from backend.document.schemas.job import (
    BulkDismissRequest,
    BulkRetryRequest,
    ProcessingJobDetailResponse,
    ProcessingJobResponse,
    RetryJobRequest,
)

router = APIRouter(prefix="/workspaces/{workspace_id}/jobs", tags=["Jobs"])


@router.get("/dlq", response_model=list[ProcessingJobResponse])
async def list_dlq_jobs(
    workspace_id: uuid.UUID,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    error_code: str | None = Query(None),
    session: AsyncSession = Depends(get_async_session),
    _=Depends(require_role(["admin", "owner", "member"])),
):
    """List jobs currently in the Dead Letter Queue for a specific workspace."""
    repo = JobRepository()
    return await repo.list_dlq_jobs(str(workspace_id), page, size, session, error_code=error_code)


@router.get("/{job_id}", response_model=ProcessingJobDetailResponse)
async def get_job_details(
    workspace_id: uuid.UUID,
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    _=Depends(require_role(["admin", "owner", "member"])),
):
    """Get detailed state of a processing job, including steps, audit logs, and DLQ diagnostics."""
    job_repo = JobRepository()
    step_repo = JobStepRepository()
    audit_repo = JobAuditRepository()
    failed_job_repo = FailedJobRepository()

    job = await job_repo.get_by_id(job_id, session)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    steps = await step_repo.get_completed_steps(job_id, session)
    audits = await audit_repo.list_for_job(job_id, session)
    diagnostics = await failed_job_repo.get_by_job_id(job_id, session)

    return {
        "id": job.id,
        "document_id": job.document_id,
        "batch_id": job.batch_id,
        "version_id": job.version_id,
        "status": job.status,
        "current_step": job.current_step,
        "priority": job.priority,
        "retry_count": job.retry_count,
        "max_retries": job.max_retries,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "error_code": job.error_code,
        "error_message": job.error_message,
        "step_metrics": job.step_metrics,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "dlq_reason": job.dlq_reason,
        "dlq_at": job.dlq_at,
        "steps": steps,
        "audits": audits,
        "diagnostics": diagnostics,
    }


@router.post("/{job_id}/retry")
async def retry_job(
    workspace_id: uuid.UUID,
    job_id: uuid.UUID,
    request: RetryJobRequest,
    session: AsyncSession = Depends(get_async_session),
    _=Depends(require_role(["admin", "owner"])),
):
    """Retry a failed or DLQ job, optionally resuming from a specific step."""
    job_repo = JobRepository()
    failed_job_repo = FailedJobRepository()
    audit_repo = JobAuditRepository()

    job = await job_repo.get_by_id(job_id, session)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status not in {"FAILED", "DLQ", "CANCELLED"}:
        raise HTTPException(
            status_code=400,
            detail="Job must be in FAILED, DLQ, or CANCELLED state to retry",
        )

    await job_repo.reset_job_for_retry(
        job_id=job_id,
        session=session,
        resume_from_step=request.resume_from_step,
    )
    await failed_job_repo.update_remediation_status(
        job_id=job_id, status="RESOLVED_REPLAY", user_id=None, session=session
    )
    await audit_repo.append(
        job_id=job_id,
        event="JOB_RETRY_REQUESTED",
        actor="operator_api",
        payload={"resume_from_step": request.resume_from_step},
        session=session,
    )

    # Dispatch back to Celery pipeline
    try:
        from backend.document.workers.ingestion import process_document_job
        process_document_job.apply_async(
            kwargs={
                "job_id": str(job.id),
                "document_id": str(job.document_id),
                "tenant_id": str(workspace_id),
            },
            queue="ingestion",
        )
    except Exception:
        pass

    return {"message": "Job successfully queued for retry", "job_id": str(job_id)}


@router.post("/dlq/bulk-retry")
async def bulk_retry_dlq_jobs(
    workspace_id: uuid.UUID,
    request: BulkRetryRequest,
    session: AsyncSession = Depends(get_async_session),
    _=Depends(require_role(["admin", "owner"])),
):
    """Bulk retry DLQ jobs matching ID list or error code filter."""
    job_repo = JobRepository()
    failed_job_repo = FailedJobRepository()
    audit_repo = JobAuditRepository()

    target_jobs: list[uuid.UUID] = []
    if request.job_ids:
        target_jobs = request.job_ids
    else:
        dlq_list = await job_repo.list_dlq_jobs(
            tenant_id=str(workspace_id),
            page=1,
            size=100,
            session=session,
            error_code=request.error_code_filter,
        )
        target_jobs = [j.id for j in dlq_list]

    requeued_count = 0
    for jid in target_jobs:
        job = await job_repo.get_by_id(jid, session)
        if job and job.status in {"FAILED", "DLQ", "CANCELLED"}:
            await job_repo.reset_job_for_retry(
                job_id=jid, session=session, resume_from_step=request.resume_from_step
            )
            await failed_job_repo.update_remediation_status(
                job_id=jid, status="RESOLVED_REPLAY", user_id=None, session=session
            )
            await audit_repo.append(
                job_id=jid,
                event="JOB_BULK_RETRY_REQUESTED",
                actor="operator_api",
                payload={"resume_from_step": request.resume_from_step},
                session=session,
            )
            try:
                from backend.document.workers.ingestion import process_document_job
                process_document_job.apply_async(
                    kwargs={
                        "job_id": str(job.id),
                        "document_id": str(job.document_id),
                        "tenant_id": str(workspace_id),
                    },
                    queue="ingestion",
                )
            except Exception:
                pass
            requeued_count += 1

    return {"message": f"Successfully requeued {requeued_count} jobs", "count": requeued_count}


@router.post("/dlq/bulk-dismiss")
async def bulk_dismiss_dlq_jobs(
    workspace_id: uuid.UUID,
    request: BulkDismissRequest,
    session: AsyncSession = Depends(get_async_session),
    _=Depends(require_role(["admin", "owner"])),
):
    """Bulk dismiss quarantined failed jobs."""
    failed_job_repo = FailedJobRepository()
    dismissed_count = await failed_job_repo.bulk_dismiss(
        job_ids=request.job_ids,
        tenant_id=str(workspace_id),
        user_id=None,
        session=session,
    )
    return {"message": f"Successfully dismissed {dismissed_count} jobs", "count": dismissed_count}
