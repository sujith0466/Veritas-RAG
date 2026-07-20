"""FastAPI REST endpoints for Dashboard aggregations (`/api/v1/dashboard`)."""

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Request, status
import structlog

from backend.api.v1.schemas.common import ResponseMetadata, SuccessResponse
from backend.modules.dashboard.api.dependencies import DashboardAuth, get_dashboard_service
from backend.modules.dashboard.schemas.dashboard_dto import (
    ExecutiveDashboardDTO,
    KnowledgeIntelligenceSummaryDTO,
)
from backend.modules.dashboard.services.dashboard_service import DashboardService

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Dashboard & Knowledge Intelligence"])


def _build_metadata(request: Request) -> ResponseMetadata:
    """Construct standard response envelope metadata from request context."""
    req_id = getattr(request.state, "correlation_id", str(uuid4()))
    return ResponseMetadata(request_id=req_id)


@router.get(
    "/executive",
    response_model=SuccessResponse[ExecutiveDashboardDTO],
    status_code=status.HTTP_200_OK,
    summary="Get executive dashboard high-level metrics and activity",
)
async def get_executive_dashboard(
    request_ctx: Request,
    service: Annotated[DashboardService, Depends(get_dashboard_service)],
    auth: DashboardAuth,
    x_tenant_id: Annotated[str, Header(alias="X-Tenant-ID")] = "default_tenant",
) -> SuccessResponse[ExecutiveDashboardDTO]:
    """Fetch high-level executive summary across all system activity."""
    data = await service.get_executive_dashboard(tenant_id=x_tenant_id)
    return SuccessResponse(data=data, metadata=_build_metadata(request_ctx))


@router.get(
    "/knowledge-intelligence",
    response_model=SuccessResponse[KnowledgeIntelligenceSummaryDTO],
    status_code=status.HTTP_200_OK,
    summary="Get knowledge layer foundation intelligence summary",
)
async def get_knowledge_intelligence(
    request_ctx: Request,
    service: Annotated[DashboardService, Depends(get_dashboard_service)],
    auth: DashboardAuth,
    x_tenant_id: Annotated[str, Header(alias="X-Tenant-ID")] = "default_tenant",
) -> SuccessResponse[KnowledgeIntelligenceSummaryDTO]:
    """Fetch aggregated metrics across documents, chunks, embeddings, and vector storage."""
    data = await service.get_knowledge_intelligence_summary(tenant_id=x_tenant_id)
    return SuccessResponse(data=data, metadata=_build_metadata(request_ctx))
