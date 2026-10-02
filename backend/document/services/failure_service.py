"""Pipeline Failure State Synchronization Service (`PipelineFailureSynchronizer`).

Enforces consistent failure state transitions across Document, ProcessingJob, EmbeddingJob,
FailedJobDiagnostics, and DocumentEventLog, eliminating infinite intermediate states
(e.g., PROCESSING, CHUNKING, EMBEDDING, VECTOR_SYNC forever).
"""

from datetime import datetime, timezone
import traceback
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.document.models.document import Document
from backend.document.models.event_log import DocumentEventLog
from backend.document.models.failed_job import FailedJobDiagnostics
from backend.document.models.job import ProcessingJob
from backend.document.models.status import DocumentStatus
from backend.modules.embedding.models.embedding_job import EmbeddingJob

logger = structlog.get_logger(__name__)


class PipelineFailureSynchronizer:
    """Synchronizes terminal failure state across database models and event logs."""

    @classmethod
    async def record_pipeline_failure(
        cls,
        session: AsyncSession,
        document_id: uuid.UUID,
        failing_stage: str,
        error_code: str,
        error_message: str,
        exception: Exception | None = None,
        job_id: uuid.UUID | None = None,
        embedding_job_id: uuid.UUID | None = None,
        tenant_id: str | None = None,
        worker_context: dict[str, Any] | None = None,
    ) -> None:
        """Atomically transition document and related jobs to terminal FAILED state."""
        now = datetime.now(timezone.utc)
        safe_error_code = str(error_code)[:50]
        safe_error_msg = str(error_message)

        # 1. Update Document status to FAILED
        doc = await session.get(Document, document_id)
        resolved_tenant_id = tenant_id or (doc.tenant_id if doc else "unknown")
        if doc:
            doc.status = DocumentStatus.FAILED
            doc.updated_at = now

        # 2. Update ProcessingJob if present or find document's active processing job
        target_job: ProcessingJob | None = None
        if job_id:
            target_job = await session.get(ProcessingJob, job_id)
        elif doc:
            job_stmt = (
                select(ProcessingJob)
                .where(
                    ProcessingJob.document_id == document_id,
                    ProcessingJob.is_deleted.is_(False),
                )
                .order_by(ProcessingJob.created_at.desc())
                .limit(1)
            )
            target_job = (await session.execute(job_stmt)).scalar_one_or_none()

        if target_job:
            target_job.status = "FAILED"
            target_job.error_code = safe_error_code
            target_job.error_message = safe_error_msg
            target_job.completed_at = now
            target_job.updated_at = now

        # 3. Update EmbeddingJob if embedding failed
        if failing_stage == "embedding":
            emb_job: EmbeddingJob | None = None
            if embedding_job_id:
                emb_job = await session.get(EmbeddingJob, embedding_job_id)
            elif doc:
                emb_stmt = (
                    select(EmbeddingJob)
                    .where(
                        EmbeddingJob.document_id == document_id,
                        EmbeddingJob.is_deleted.is_(False),
                    )
                    .order_by(EmbeddingJob.created_at.desc())
                    .limit(1)
                )
                emb_job = (await session.execute(emb_stmt)).scalar_one_or_none()

            if emb_job:
                emb_job.status = "FAILED"
                emb_job.error_message = safe_error_msg
                emb_job.completed_at = now
                emb_job.updated_at = now

        # 4. Record Forensic Diagnostic Entry in failed_job_diagnostics if job exists
        if target_job:
            try:
                stack = traceback.format_exc() if exception else None
                diag = FailedJobDiagnostics(
                    job_id=target_job.id,
                    tenant_id=resolved_tenant_id,
                    failing_step=failing_stage,
                    exception_class=type(exception).__name__ if exception else "PipelineStageError",
                    stack_trace=stack,
                    worker_context=worker_context or {},
                    payload_snapshot={
                        "document_id": str(document_id),
                        "failing_stage": failing_stage,
                        "error_code": safe_error_code,
                        "error_message": safe_error_msg,
                    },
                    remediation_status="PENDING_TRIAGE",
                )
                session.add(diag)
            except Exception as diag_err:
                logger.warning(
                    "Failed to create FailedJobDiagnostics record",
                    document_id=str(document_id),
                    error=str(diag_err),
                )

        # 5. Append DocumentEventLog
        try:
            event_log = DocumentEventLog(
                document_id=document_id,
                job_id=target_job.id if target_job else None,
                event_type="DOCUMENT_FAILED",
                payload={
                    "stage": failing_stage,
                    "error_code": safe_error_code,
                    "error_message": safe_error_msg,
                    "tenant_id": resolved_tenant_id,
                    "timestamp": now.isoformat(),
                },
                triggered_by=f"worker_{failing_stage}",
            )
            session.add(event_log)
        except Exception as event_err:
            logger.warning(
                "Failed to append failure DocumentEventLog",
                document_id=str(document_id),
                error=str(event_err),
            )

        # 6. Commit synchronization
        await session.commit()
        logger.info(
            "Pipeline failure synchronized cleanly",
            document_id=str(document_id),
            stage=failing_stage,
            error_code=safe_error_code,
        )
