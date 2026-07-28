from fastapi import APIRouter, Depends, Request, HTTPException, status

from backend.api.v1.schemas.common import ResponseMetadata, SuccessResponse
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import get_db
from backend.modules.dashboard.schemas.dashboard_dto import (
    AuditExportBundleDTO, AuditExportRequestDTO, ExecutiveDashboardDTO,
    HallucinationTrendDTO, SLAComplianceReportDTO, KnowledgeIntelligenceSummaryDTO)
from backend.modules.dashboard.services.audit_export import AuditExportService
from backend.modules.dashboard.services.dashboard_service import \
    DashboardService
from sqlalchemy.ext.asyncio import AsyncSession

# NOTE: This router is mounted at /dashboard by the v1 router.
# The internal /v1 prefix was removed to align with the frontend client.
router = APIRouter(prefix="", tags=["Dashboard"])


def get_dashboard_service(session: AsyncSession = Depends(get_db)) -> DashboardService:
    return DashboardService(session)


def get_audit_service():
    return AuditExportService()


def _meta(request: Request) -> ResponseMetadata:
    return ResponseMetadata(
        request_id=request.headers.get("x-correlation-id", "n/a")
    )


@router.get("/executive", response_model=SuccessResponse[ExecutiveDashboardDTO])
async def get_executive(
    request: Request,
    user: UserContext = Depends(get_current_user),
    svc: DashboardService = Depends(get_dashboard_service),
) -> SuccessResponse[ExecutiveDashboardDTO]:
    """Return executive dashboard for the current authenticated user's tenant."""
    data = await svc.get_executive_dashboard(user.tenant_id)
    return SuccessResponse(data=data, metadata=_meta(request))


@router.get("/knowledge-intelligence", response_model=SuccessResponse[KnowledgeIntelligenceSummaryDTO])
async def get_knowledge_intelligence(
    request: Request,
    user: UserContext = Depends(get_current_user),
    svc: DashboardService = Depends(get_dashboard_service),
) -> SuccessResponse[KnowledgeIntelligenceSummaryDTO]:
    """Return knowledge intelligence dashboard for the current tenant."""
    data = await svc.get_knowledge_intelligence_summary(user.tenant_id)
    return SuccessResponse(data=data, metadata=_meta(request))



@router.get("/executive/{tenant_id}", response_model=SuccessResponse[ExecutiveDashboardDTO])
async def get_executive_by_tenant(
    tenant_id: str,
    request: Request,
    user: UserContext = Depends(get_current_user),
    svc: DashboardService = Depends(get_dashboard_service),
) -> SuccessResponse[ExecutiveDashboardDTO]:
    """Return executive dashboard for a specific tenant (admin use)."""
    if user.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access forbidden.")
    data = await svc.get_executive_dashboard(tenant_id)
    return SuccessResponse(data=data, metadata=_meta(request))


@router.get("/governance", response_model=SuccessResponse[SLAComplianceReportDTO])
async def get_governance(
    request: Request,
    window: str = "24h",
    user: UserContext = Depends(get_current_user),
    svc: DashboardService = Depends(get_dashboard_service),
) -> SuccessResponse[SLAComplianceReportDTO]:
    data = await svc.get_governance_report(user.tenant_id, window)
    return SuccessResponse(data=data, metadata=_meta(request))


@router.get("/governance/{tenant_id}", response_model=SuccessResponse[SLAComplianceReportDTO])
async def get_governance_by_tenant(
    tenant_id: str,
    request: Request,
    window: str = "24h",
    user: UserContext = Depends(get_current_user),
    svc: DashboardService = Depends(get_dashboard_service),
) -> SuccessResponse[SLAComplianceReportDTO]:
    if user.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access forbidden.")
    data = await svc.get_governance_report(tenant_id, window)
    return SuccessResponse(data=data, metadata=_meta(request))


@router.get("/trends", response_model=SuccessResponse[list[HallucinationTrendDTO]])
async def get_trends(
    request: Request,
    window: str = "7d",
    user: UserContext = Depends(get_current_user),
    svc: DashboardService = Depends(get_dashboard_service),
) -> SuccessResponse[list[HallucinationTrendDTO]]:
    data = await svc.get_trust_trends(user.tenant_id, window)
    return SuccessResponse(data=data, metadata=_meta(request))


@router.get("/trends/{tenant_id}", response_model=SuccessResponse[list[HallucinationTrendDTO]])
async def get_trends_by_tenant(
    tenant_id: str,
    request: Request,
    window: str = "7d",
    user: UserContext = Depends(get_current_user),
    svc: DashboardService = Depends(get_dashboard_service),
) -> SuccessResponse[list[HallucinationTrendDTO]]:
    if user.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access forbidden.")
    data = await svc.get_trust_trends(tenant_id, window)
    return SuccessResponse(data=data, metadata=_meta(request))


@router.post("/export", response_model=SuccessResponse[AuditExportBundleDTO])
async def export_audit(
    request: Request,
    body: AuditExportRequestDTO,
    svc: AuditExportService = Depends(get_audit_service),
) -> SuccessResponse[AuditExportBundleDTO]:
    data = await svc.generate_export(body)
    return SuccessResponse(data=data, metadata=_meta(request))
