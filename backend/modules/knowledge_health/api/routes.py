"""FastAPI REST endpoints for Knowledge Health & Lifecycle Management (`/api/v1/knowledge-health`)."""

from typing import Annotated, Any, Dict, List
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, Header, Query, Request, status
import structlog
from backend.api.v1.schemas.common import ResponseMetadata, SuccessResponse
from backend.modules.knowledge_health.api.dependencies import AdminAuth, get_health_orchestrator
from backend.modules.knowledge_health.schemas.health_dto import (
    HealthScanJobDTO,
    HealthScanRequestDTO,
    MigrationJobDTO,
    ModelRotationRequestDTO,
    ParityAuditDTO,
    PurgeSummaryDTO,
)
from backend.modules.knowledge_health.services.health_service import KnowledgeHealthOrchestrator

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Knowledge Health & Lifecycle"])


def _build_metadata(request: Request) -> ResponseMetadata:
    """Construct standard response envelope metadata from request context."""
    req_id = getattr(request.state, "correlation_id", str(uuid4()))
    return ResponseMetadata(request_id=req_id)


@router.post(
    "/scans",
    response_model=SuccessResponse[HealthScanJobDTO],
    status_code=status.HTTP_200_OK,
    summary="Initiate a health scan across PostgreSQL and Qdrant",
)
async def trigger_health_scan(
    request_ctx: Request,
    request: HealthScanRequestDTO,
    auth: AdminAuth,
    orchestrator: Annotated[KnowledgeHealthOrchestrator, Depends(get_health_orchestrator)],
    x_tenant_id: Annotated[str, Header(alias="X-Tenant-ID")] = "default_tenant",
) -> SuccessResponse[HealthScanJobDTO]:
    """Execute immediate audit sweep (orphan cleanup, count parity check, or model drift scan)."""
    job = await orchestrator.run_health_scan(tenant_id=x_tenant_id, scan_type=request.scan_type)
    return SuccessResponse(data=job, metadata=_build_metadata(request_ctx))


@router.get(
    "/scans",
    response_model=SuccessResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Retrieve paginated history of past health scan jobs",
)
async def list_health_scans(
    request_ctx: Request,
    auth: AdminAuth,
    orchestrator: Annotated[KnowledgeHealthOrchestrator, Depends(get_health_orchestrator)],
    scan_type: Annotated[str | None, Query(description="Filter by scan type")] = None,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    size: Annotated[int, Query(ge=1, le=100, description="Page size")] = 20,
    x_tenant_id: Annotated[str, Header(alias="X-Tenant-ID")] = "default_tenant",
) -> SuccessResponse[Dict[str, Any]]:
    """Fetch history of past scan jobs and statistical results for a tenant."""
    dtos, total = await orchestrator.list_scan_jobs(tenant_id=x_tenant_id, scan_type=scan_type, page=page, size=size)
    return SuccessResponse(
        data={"items": [item.model_dump() for item in dtos], "total": total, "page": page, "size": size},
        metadata=_build_metadata(request_ctx),
    )


@router.get(
    "/parity",
    response_model=SuccessResponse[ParityAuditDTO],
    status_code=status.HTTP_200_OK,
    summary="Check real-time 1:1 count parity between DB and vector store",
)
async def check_parity(
    request_ctx: Request,
    auth: AdminAuth,
    orchestrator: Annotated[KnowledgeHealthOrchestrator, Depends(get_health_orchestrator)],
    x_tenant_id: Annotated[str, Header(alias="X-Tenant-ID")] = "default_tenant",
) -> SuccessResponse[ParityAuditDTO]:
    """Verify exact count alignment between embedded PostgreSQL chunks and Qdrant points."""
    dto = await orchestrator.verify_parity(tenant_id=x_tenant_id)
    return SuccessResponse(data=dto, metadata=_build_metadata(request_ctx))


@router.post(
    "/rotate-model",
    response_model=SuccessResponse[MigrationJobDTO],
    status_code=status.HTTP_200_OK,
    summary="Trigger shadow collection migration and re-embedding for model rotation",
)
async def rotate_model(
    request_ctx: Request,
    request: ModelRotationRequestDTO,
    auth: AdminAuth,
    orchestrator: Annotated[KnowledgeHealthOrchestrator, Depends(get_health_orchestrator)],
    x_tenant_id: Annotated[str, Header(alias="X-Tenant-ID")] = "default_tenant",
) -> SuccessResponse[MigrationJobDTO]:
    """Identify stale chunks and enqueue shadow re-indexing campaign (`ADR-M6-002`)."""
    dto = await orchestrator.rotate_tenant_embedding_model(
        tenant_id=x_tenant_id,
        new_provider=request.new_provider,
        new_model=request.new_model,
    )
    return SuccessResponse(data=dto, metadata=_build_metadata(request_ctx))


@router.delete(
    "/purge/{document_id}",
    response_model=SuccessResponse[PurgeSummaryDTO],
    status_code=status.HTTP_200_OK,
    summary="Execute explicit two-phase hard purge for a document and its vectors",
)
async def purge_document(
    request_ctx: Request,
    document_id: UUID,
    auth: AdminAuth,
    orchestrator: Annotated[KnowledgeHealthOrchestrator, Depends(get_health_orchestrator)],
    x_tenant_id: Annotated[str, Header(alias="X-Tenant-ID")] = "default_tenant",
) -> SuccessResponse[PurgeSummaryDTO]:
    """Atomically remove document vectors from Qdrant and execute DB hard delete (`ADR-M6-001`)."""
    summary = await orchestrator.execute_two_phase_purge(document_id=document_id, tenant_id=x_tenant_id)
    return SuccessResponse(data=summary, metadata=_build_metadata(request_ctx))
