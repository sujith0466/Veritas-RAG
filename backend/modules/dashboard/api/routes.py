from fastapi import APIRouter, Depends, HTTPException
from backend.modules.dashboard.schemas.dashboard_dto import (
    ExecutiveDashboardDTO, SLAComplianceReportDTO, HallucinationTrendDTO,
    AuditExportRequestDTO, AuditExportBundleDTO
)
from backend.modules.dashboard.services.dashboard_service import DashboardService
from backend.modules.dashboard.services.cache_service import RedisDashboardCache
from backend.modules.dashboard.services.audit_export import AuditExportService
from typing import List

router = APIRouter(prefix="/dashboard/v1", tags=["Dashboard"])

def get_dashboard_service():
    # In production, inject proper dependencies
    return DashboardService(RedisDashboardCache())

def get_audit_service():
    return AuditExportService()

@router.get("/executive/{tenant_id}", response_model=ExecutiveDashboardDTO)
async def get_executive(tenant_id: str, svc: DashboardService = Depends(get_dashboard_service)):
    return await svc.get_executive_dashboard(tenant_id)

@router.get("/governance/{tenant_id}", response_model=SLAComplianceReportDTO)
async def get_governance(tenant_id: str, window: str = "24h", svc: DashboardService = Depends(get_dashboard_service)):
    return await svc.get_governance_report(tenant_id, window)

@router.get("/trends/{tenant_id}", response_model=List[HallucinationTrendDTO])
async def get_trends(tenant_id: str, window: str = "7d", svc: DashboardService = Depends(get_dashboard_service)):
    return await svc.get_trust_trends(tenant_id, window)

@router.post("/export", response_model=AuditExportBundleDTO)
async def export_audit(request: AuditExportRequestDTO, svc: AuditExportService = Depends(get_audit_service)):
    return await svc.generate_export(request)
