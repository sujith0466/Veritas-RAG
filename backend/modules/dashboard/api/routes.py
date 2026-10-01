from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.v1.schemas.common import ResponseMetadata, SuccessResponse
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import get_db
from backend.modules.dashboard.schemas.dashboard_dto import (
    AuditExportBundleDTO,
    AuditExportRequestDTO,
    CommandCenterDTO,
    ExecutiveDashboardDTO,
    HallucinationTrendDTO,
    KnowledgeIntelligenceSummaryDTO,
    QueryExecutionLedgerDTO,
    QueryExecutionTraceDTO,
    SLAComplianceReportDTO,
)
from backend.modules.dashboard.services.audit_export import AuditExportService
from backend.modules.dashboard.services.command_center_service import CommandCenterService
from backend.modules.dashboard.services.dashboard_service import DashboardService
from backend.modules.dashboard.services.execution_intelligence_service import (
    ExecutionIntelligenceService,
)

# NOTE: This router is mounted at /dashboard by the v1 router.
# The internal /v1 prefix was removed to align with the frontend client.
router = APIRouter(prefix="", tags=["Dashboard"])


def get_dashboard_service(session: AsyncSession = Depends(get_db)) -> DashboardService:
    return DashboardService(session)


def get_command_center_service(session: AsyncSession = Depends(get_db)) -> CommandCenterService:
    return CommandCenterService(session)


def get_execution_intelligence_service(
    session: AsyncSession = Depends(get_db),
) -> ExecutionIntelligenceService:
    return ExecutionIntelligenceService(session)


def get_audit_service():
    return AuditExportService()


def _meta(request: Request) -> ResponseMetadata:
    return ResponseMetadata(
        request_id=request.headers.get("x-correlation-id", "n/a")
    )


@router.get("/command-center", response_model=SuccessResponse[CommandCenterDTO])
async def get_command_center(
    request: Request,
    time_window: str = Query("24h", pattern="^(1h|24h|7d|30d|all)$"),
    user: UserContext = Depends(get_current_user),
    svc: CommandCenterService = Depends(get_command_center_service),
) -> SuccessResponse[CommandCenterDTO]:
    """Return consolidated Enterprise AI Reliability Command Center telemetry."""
    data = await svc.get_command_center(user.tenant_id, time_window=time_window)
    return SuccessResponse(data=data, metadata=_meta(request))


@router.get("/executions", response_model=SuccessResponse[QueryExecutionLedgerDTO])
async def get_executions(
    request: Request,
    time_window: str = Query("24h", pattern="^(1h|24h|7d|30d|all)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None),
    search: str | None = Query(None),
    min_reliability: float | None = Query(None, ge=0.0, le=1.0),
    user: UserContext = Depends(get_current_user),
    svc: ExecutionIntelligenceService = Depends(get_execution_intelligence_service),
) -> SuccessResponse[QueryExecutionLedgerDTO]:
    """Return paginated execution ledger for the tenant."""
    data = await svc.list_executions(
        tenant_id=user.tenant_id,
        time_window=time_window,
        limit=limit,
        offset=offset,
        status=status,
        search=search,
        min_reliability=min_reliability,
    )
    return SuccessResponse(data=data, metadata=_meta(request))


@router.get("/executions/{query_id}/trace", response_model=SuccessResponse[QueryExecutionTraceDTO])
async def get_execution_trace(
    query_id: str,
    request: Request,
    user: UserContext = Depends(get_current_user),
    svc: ExecutionIntelligenceService = Depends(get_execution_intelligence_service),
) -> SuccessResponse[QueryExecutionTraceDTO]:
    """Return deep forensic trace for a specific execution, enforcing tenant isolation."""
    data = await svc.get_execution_trace(tenant_id=user.tenant_id, query_id=query_id)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution record not found or access forbidden for this tenant.",
        )
    return SuccessResponse(data=data, metadata=_meta(request))


@router.get("/executive", response_model=SuccessResponse[ExecutiveDashboardDTO])
async def get_executive(
    request: Request,
    time_window: str = Query("24h", pattern="^(1h|24h|7d|30d|all)$"),
    user: UserContext = Depends(get_current_user),
    svc: DashboardService = Depends(get_dashboard_service),
) -> SuccessResponse[ExecutiveDashboardDTO]:
    """Return executive dashboard for the current authenticated user's tenant."""
    data = await svc.get_executive_dashboard(user.tenant_id, time_window=time_window)
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
    time_window: str = Query("24h", pattern="^(1h|24h|7d|30d|all)$"),
    user: UserContext = Depends(get_current_user),
    svc: DashboardService = Depends(get_dashboard_service),
) -> SuccessResponse[ExecutiveDashboardDTO]:
    """Return executive dashboard for a specific tenant (admin use)."""
    if user.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access forbidden.")
    data = await svc.get_executive_dashboard(tenant_id, time_window=time_window)
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
