"""Admin Document Pipeline Diagnostics API (`ADR-005 / Phase D2.7`).

Provides operational health, stranded job metrics, storage discrepancy audits,
and non-destructive reconciliation reporting for operators and platform admins.
"""

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.api.v1.schemas.common import ResponseMetadata, SuccessResponse
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import get_db
from backend.core.dependencies.rbac import require_role
from backend.core.permissions.rbac import Role
from backend.document.models.document import Document
from backend.document.models.job import DispatchState, ProcessingJob
from backend.document.services.reconciliation import (
    DocumentReconciliationService,
    ReconciliationReport,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/admin/documents", tags=["Admin Document Diagnostics"])


class PipelineHealthSummary(BaseModel):
    """Aggregated reconciliation counters."""

    total_documents: int
    healthy_ready: int
    class_a_intact_storage: int
    class_b_missing_storage: int
    class_c_failed: int
    other_discrepancies: int
    scanned_at: str
    dry_run: bool = True


class PipelineHealthData(BaseModel):
    """Payload for pipeline health diagnostics."""

    status: str = Field(..., description="Overall health: HEALTHY, DEGRADED, or CRITICAL")
    tenant_id: str = Field(..., description="Tenant ID or ALL for platform-wide")
    stranded_jobs_count: int = Field(..., description="Jobs stuck in PENDING > 10m or FAILED_DISPATCH")
    storage_discrepancies_count: int = Field(..., description="Documents missing underlying storage objects")
    qdrant_parity_drift_count: int = Field(..., description="READY documents with chunk/vector count mismatches")
    active_jobs_count: int = Field(..., description="Inflight background jobs currently running")
    summary: PipelineHealthSummary
    recommendations: list[str]
    items: list[dict[str, Any]] | None = None


def _build_metadata(request: Request) -> ResponseMetadata:
    req_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    return ResponseMetadata(request_id=req_id)


def _resolve_target_tenant(
    user: UserContext,
    workspace_id: uuid.UUID | None,
) -> str | None:
    user_role = Role.from_str(user.role) if isinstance(user.role, str) else user.role
    if user_role == Role.PLATFORM_ADMIN:
        return str(workspace_id) if workspace_id else None

    user_tenant = getattr(user, "tenant_id", None)
    if not user_tenant:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing workspace context for admin diagnostics",
        )
    if workspace_id and str(workspace_id) != str(user_tenant):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Cannot view pipeline diagnostics for another workspace",
        )
    return str(user_tenant)


@router.get(
    "/pipeline-health",
    response_model=SuccessResponse[PipelineHealthData],
    summary="Get document pipeline health and stranded job diagnostics",
)
async def get_pipeline_health(
    request: Request,
    workspace_id: uuid.UUID | None = Query(None, description="Optional workspace filter"),
    include_items: bool = Query(False, description="Include granular itemized classifications"),
    limit: int = Query(500, ge=1, le=1000, description="Max documents to audit"),
    user: UserContext = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse[PipelineHealthData]:
    """Retrieve operational diagnostics for the document ingestion pipeline.

    Calculates stranded jobs, storage discrepancies, vector parity drift, and
    reconciliation classifications in strict read-only mode.
    """
    target_tenant = _resolve_target_tenant(user, workspace_id)

    # 1. Stranded jobs query (PENDING older than 10 mins OR FAILED_DISPATCH)
    now_utc = datetime.now(timezone.utc)
    ten_mins_ago = now_utc - timedelta(minutes=10)

    stranded_filter = or_(
        (ProcessingJob.status == "PENDING") & (ProcessingJob.created_at < ten_mins_ago),
        ProcessingJob.dispatch_state == DispatchState.FAILED_DISPATCH.value,
    )

    stranded_stmt = (
        select(func.count(ProcessingJob.id))
        .join(Document, ProcessingJob.document_id == Document.id)
        .where(
            stranded_filter,
            ProcessingJob.is_deleted.is_(False),
            Document.is_deleted.is_(False),
        )
    )
    if target_tenant:
        stranded_stmt = stranded_stmt.where(Document.tenant_id == target_tenant)

    stranded_res = await session.scalar(stranded_stmt)
    stranded_count = int(stranded_res) if isinstance(stranded_res, (int, float)) else 0

    # 2. Active jobs query
    active_stmt = (
        select(func.count(ProcessingJob.id))
        .join(Document, ProcessingJob.document_id == Document.id)
        .where(
            ProcessingJob.status.in_(["CLAIMED", "DISPATCHED", "PROCESSING"]),
            ProcessingJob.is_deleted.is_(False),
            Document.is_deleted.is_(False),
        )
    )
    if target_tenant:
        active_stmt = active_stmt.where(Document.tenant_id == target_tenant)

    active_res = await session.scalar(active_stmt)
    active_count = int(active_res) if isinstance(active_res, (int, float)) else 0

    # 3. Read-only reconciliation scan
    report: ReconciliationReport = await DocumentReconciliationService.scan_tenant(
        tenant_id=target_tenant,
        session=session,
        dry_run=True,
        limit=limit,
    )

    storage_discrepancies = report.class_b_count
    parity_drift = report.other_discrepancy_count

    # 4. Status evaluation
    if storage_discrepancies > 0 or stranded_count > 10:
        health_status = "CRITICAL"
    elif stranded_count > 0 or parity_drift > 0:
        health_status = "DEGRADED"
    else:
        health_status = "HEALTHY"

    # 5. Recommendations formulation
    recommendations: list[str] = []
    if report.class_a_count > 0:
        recommendations.append(
            f"{report.class_a_count} document(s) have intact storage but missing chunks/vectors (Class A). Execute controlled canary recovery."
        )
    if report.class_b_count > 0:
        recommendations.append(
            f"{report.class_b_count} document(s) are missing underlying storage files (Class B). Mark as FAILED (STORAGE_OBJECT_NOT_FOUND) or quarantine."
        )
    if stranded_count > 0:
        recommendations.append(
            f"{stranded_count} processing job(s) stranded in queue or failed dispatch. Run automated job sweeper."
        )
    if parity_drift > 0:
        recommendations.append(
            f"{parity_drift} document(s) show vector index parity drift. Inspect embedding/Qdrant sync pipeline."
        )
    if not recommendations:
        recommendations.append("Document ingestion pipeline is operating with 100% integrity.")

    summary = PipelineHealthSummary(
        total_documents=report.total_documents,
        healthy_ready=report.healthy_count,
        class_a_intact_storage=report.class_a_count,
        class_b_missing_storage=report.class_b_count,
        class_c_failed=report.class_c_count,
        other_discrepancies=report.other_discrepancy_count,
        scanned_at=report.scanned_at,
        dry_run=report.dry_run,
    )

    data = PipelineHealthData(
        status=health_status,
        tenant_id=target_tenant or "ALL",
        stranded_jobs_count=stranded_count,
        storage_discrepancies_count=storage_discrepancies,
        qdrant_parity_drift_count=parity_drift,
        active_jobs_count=active_count,
        summary=summary,
        recommendations=recommendations,
        items=[asdict(it) for it in report.items] if include_items else None,
    )

    return SuccessResponse(
        success=True,
        data=data,
        metadata=_build_metadata(request),
    )


@router.post(
    "/reconcile",
    response_model=SuccessResponse[dict[str, Any]],
    summary="Trigger non-destructive dry-run pipeline reconciliation scan",
)
async def trigger_reconciliation_scan(
    request: Request,
    workspace_id: uuid.UUID | None = Query(None, description="Optional workspace filter"),
    dry_run: bool = Query(True, description="Strictly dry-run audit (read-only)"),
    format: str = Query("json", pattern="^(json|markdown)$", description="Report format: json or markdown"),
    limit: int = Query(500, ge=1, le=1000, description="Max documents to audit"),
    user: UserContext = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse[dict[str, Any]]:
    """Execute a dry-run reconciliation scan across document records."""
    if not dry_run:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mutating execution mode is disabled. Use controlled recovery playbook D2.8.",
        )

    target_tenant = _resolve_target_tenant(user, workspace_id)

    report = await DocumentReconciliationService.scan_tenant(
        tenant_id=target_tenant,
        session=session,
        dry_run=True,
        limit=limit,
    )

    if format == "markdown":
        result = {"report_markdown": report.to_markdown()}
    else:
        result = report.to_dict()

    return SuccessResponse(
        success=True,
        data=result,
        metadata=_build_metadata(request),
    )
