"""FastAPI REST endpoints for Query Analytics (`/api/v1/analytics`)."""

from datetime import datetime
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.api.v1.schemas.common import ResponseMetadata, SuccessResponse
from backend.core.dependencies.database import get_db as get_db_session
from backend.modules.analytics.api.dependencies import AnalyticsAuth, get_analytics_service, get_reporting_service
from backend.modules.analytics.schemas.analytics_dto import (
    AnalyticsFilterDTO,
    ConfidenceAnalyticsDTO,
    LatencyAnalyticsDTO,
    QueryHistoryListDTO,
    QueryTrendsDTO,
    ReliabilityHistoryDTO,
    SearchAnalyticsDTO,
    SuccessRateDTO,
    QueryTraceDetailDTO,
    QuerySandboxRequestDTO,
    QuerySandboxResponseDTO,
)
from backend.modules.analytics.schemas.reporting_dto import (
    ReportExportRequestDTO,
    ReportMetadataDTO,
    ReportFormat,
)
from backend.modules.analytics.services.analytics_service import QueryAnalyticsService
from backend.modules.analytics.services.reporting_service import ReportingService

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Query Analytics & Reliability"])


def _build_metadata(request: Request) -> ResponseMetadata:
    """Construct standard response envelope metadata from request context."""
    req_id = getattr(request.state, "correlation_id", str(uuid4()))
    return ResponseMetadata(request_id=req_id)


@router.get(
    "/history",
    response_model=SuccessResponse[QueryHistoryListDTO],
    status_code=status.HTTP_200_OK,
    summary="List paginated query execution history",
)
async def get_query_history(
    request_ctx: Request,
    service: Annotated[QueryAnalyticsService, Depends(get_analytics_service)],
    auth: AnalyticsAuth,
    page: int = Query(1, ge=1, description="Page index (1-indexed)"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    outcome: str | None = Query(None, description="Optional filter by outcome status"),
    start_time: datetime | None = Query(None, description="Start timestamp filter"),
    end_time: datetime | None = Query(None, description="End timestamp filter"),
    x_tenant_id: Annotated[str, Header(alias="X-Tenant-ID")] = "default_tenant",
) -> SuccessResponse[QueryHistoryListDTO]:
    """Fetch paginated AI query history records for the tenant."""
    data = await service.get_query_history(
        tenant_id=x_tenant_id,
        page=page,
        page_size=page_size,
        outcome_filter=outcome,
        start_time=start_time,
        end_time=end_time,
    )
    return SuccessResponse(data=data, metadata=_build_metadata(request_ctx))


@router.get(
    "/success-rate",
    response_model=SuccessResponse[SuccessRateDTO],
    status_code=status.HTTP_200_OK,
    summary="Get success, clarification, and failure rate KPIs",
)
async def get_success_rate(
    request_ctx: Request,
    service: Annotated[QueryAnalyticsService, Depends(get_analytics_service)],
    auth: AnalyticsAuth,
    start_time: datetime | None = Query(None, description="Start timestamp filter"),
    end_time: datetime | None = Query(None, description="End timestamp filter"),
    x_tenant_id: Annotated[str, Header(alias="X-Tenant-ID")] = "default_tenant",
) -> SuccessResponse[SuccessRateDTO]:
    """Calculate overall success percentage and retry rates."""
    filter_dto = AnalyticsFilterDTO(tenant_id=x_tenant_id, start_time=start_time, end_time=end_time)
    data = await service.get_success_rate(filter_dto)
    return SuccessResponse(data=data, metadata=_build_metadata(request_ctx))


@router.get(
    "/latency",
    response_model=SuccessResponse[LatencyAnalyticsDTO],
    status_code=status.HTTP_200_OK,
    summary="Get P50, P90, P95, and P99 latency distribution",
)
async def get_latency_analytics(
    request_ctx: Request,
    service: Annotated[QueryAnalyticsService, Depends(get_analytics_service)],
    auth: AnalyticsAuth,
    start_time: datetime | None = Query(None, description="Start timestamp filter"),
    end_time: datetime | None = Query(None, description="End timestamp filter"),
    x_tenant_id: Annotated[str, Header(alias="X-Tenant-ID")] = "default_tenant",
) -> SuccessResponse[LatencyAnalyticsDTO]:
    """Calculate execution latency distribution percentiles."""
    filter_dto = AnalyticsFilterDTO(tenant_id=x_tenant_id, start_time=start_time, end_time=end_time)
    data = await service.get_latency_analytics(filter_dto)
    return SuccessResponse(data=data, metadata=_build_metadata(request_ctx))


@router.get(
    "/confidence",
    response_model=SuccessResponse[ConfidenceAnalyticsDTO],
    status_code=status.HTTP_200_OK,
    summary="Get confidence score distribution statistics",
)
async def get_confidence_analytics(
    request_ctx: Request,
    service: Annotated[QueryAnalyticsService, Depends(get_analytics_service)],
    auth: AnalyticsAuth,
    start_time: datetime | None = Query(None, description="Start timestamp filter"),
    end_time: datetime | None = Query(None, description="End timestamp filter"),
    x_tenant_id: Annotated[str, Header(alias="X-Tenant-ID")] = "default_tenant",
) -> SuccessResponse[ConfidenceAnalyticsDTO]:
    """Calculate pre-generation confidence statistics across queries."""
    filter_dto = AnalyticsFilterDTO(tenant_id=x_tenant_id, start_time=start_time, end_time=end_time)
    data = await service.get_confidence_analytics(filter_dto)
    return SuccessResponse(data=data, metadata=_build_metadata(request_ctx))


@router.get(
    "/trends",
    response_model=SuccessResponse[QueryTrendsDTO],
    status_code=status.HTTP_200_OK,
    summary="Get time-series query volume and score trends",
)
async def get_query_trends(
    request_ctx: Request,
    service: Annotated[QueryAnalyticsService, Depends(get_analytics_service)],
    auth: AnalyticsAuth,
    interval: str = Query("daily", description="Time bucket interval: hourly, daily, weekly"),
    start_time: datetime | None = Query(None, description="Start timestamp filter"),
    end_time: datetime | None = Query(None, description="End timestamp filter"),
    x_tenant_id: Annotated[str, Header(alias="X-Tenant-ID")] = "default_tenant",
) -> SuccessResponse[QueryTrendsDTO]:
    """Compute bucketed time-series query counts and average confidence scores."""
    filter_dto = AnalyticsFilterDTO(tenant_id=x_tenant_id, interval=interval, start_time=start_time, end_time=end_time)
    data = await service.get_query_trends(filter_dto)
    return SuccessResponse(data=data, metadata=_build_metadata(request_ctx))


@router.get(
    "/reliability-history",
    response_model=SuccessResponse[ReliabilityHistoryDTO],
    status_code=status.HTTP_200_OK,
    summary="Get unified reliability score timeline and moving averages",
)
async def get_reliability_history(
    request_ctx: Request,
    service: Annotated[QueryAnalyticsService, Depends(get_analytics_service)],
    auth: AnalyticsAuth,
    interval: str = Query("daily", description="Time bucket interval: hourly, daily, weekly"),
    start_time: datetime | None = Query(None, description="Start timestamp filter"),
    end_time: datetime | None = Query(None, description="End timestamp filter"),
    x_tenant_id: Annotated[str, Header(alias="X-Tenant-ID")] = "default_tenant",
) -> SuccessResponse[ReliabilityHistoryDTO]:
    """Calculate historical unified reliability scores and moving average trendline."""
    filter_dto = AnalyticsFilterDTO(tenant_id=x_tenant_id, interval=interval, start_time=start_time, end_time=end_time)
    data = await service.get_reliability_history(filter_dto)
    return SuccessResponse(data=data, metadata=_build_metadata(request_ctx))


@router.get(
    "/search",
    response_model=SuccessResponse[SearchAnalyticsDTO],
    status_code=status.HTTP_200_OK,
    summary="Get hybrid search candidate and stage analytics",
)
async def get_search_analytics(
    request_ctx: Request,
    service: Annotated[QueryAnalyticsService, Depends(get_analytics_service)],
    auth: AnalyticsAuth,
    x_tenant_id: Annotated[str, Header(alias="X-Tenant-ID")] = "default_tenant",
) -> SuccessResponse[SearchAnalyticsDTO]:
    """Aggregate multi-stage retrieval metrics from hybrid search logs."""
    data = await service.get_search_analytics(tenant_id=x_tenant_id)
    return SuccessResponse(data=data, metadata=_build_metadata(request_ctx))


@router.get(
    "/trace/{correlation_id}",
    response_model=SuccessResponse[QueryTraceDetailDTO],
    status_code=status.HTTP_200_OK,
    summary="Get detailed forensic inspection trace for a query execution",
)
async def get_query_trace_detail(
    correlation_id: str,
    request_ctx: Request,
    service: Annotated[QueryAnalyticsService, Depends(get_analytics_service)],
    auth: AnalyticsAuth,
    x_tenant_id: Annotated[str, Header(alias="X-Tenant-ID")] = "default_tenant",
) -> SuccessResponse[QueryTraceDetailDTO]:
    """Fetch complete forensic diagnostics breakdown across stages, candidates, and self-correction steps."""
    data = await service.get_query_trace_detail(correlation_id=correlation_id, tenant_id=x_tenant_id)
    return SuccessResponse(data=data, metadata=_build_metadata(request_ctx))


@router.post(
    "/sandbox/execute",
    response_model=SuccessResponse[QuerySandboxResponseDTO],
    status_code=status.HTTP_200_OK,
    summary="Execute a live query test in the developer sandbox console",
)
async def execute_query_sandbox(
    request_dto: QuerySandboxRequestDTO,
    request_ctx: Request,
    service: Annotated[QueryAnalyticsService, Depends(get_analytics_service)],
    auth: AnalyticsAuth,
    x_tenant_id: Annotated[str, Header(alias="X-Tenant-ID")] = "default_tenant",
) -> SuccessResponse[QuerySandboxResponseDTO]:
    """Execute a test query against the AI pipeline with adjustable parameters and trace diagnostics."""
    data = await service.execute_query_sandbox(request_dto=request_dto, tenant_id=x_tenant_id)
    return SuccessResponse(data=data, metadata=_build_metadata(request_ctx))


# In-memory store for generated report downloads across API sessions
_report_cache: dict[str, tuple[bytes, ReportMetadataDTO]] = {}


@router.post(
    "/reports/export",
    response_model=SuccessResponse[ReportMetadataDTO],
    status_code=status.HTTP_200_OK,
    summary="Generate and export an enterprise PDF or JSON reliability report",
)
async def export_enterprise_report(
    request_dto: ReportExportRequestDTO,
    request_ctx: Request,
    service: Annotated[ReportingService, Depends(get_reporting_service)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    auth: AnalyticsAuth,
    x_tenant_id: Annotated[str, Header(alias="X-Tenant-ID")] = "default_tenant",
) -> SuccessResponse[ReportMetadataDTO]:
    """Generate an SLA compliance, reliability audit, or knowledge health report using ReportLab PDF."""
    if request_dto.tenant_id == "default" and x_tenant_id != "default_tenant":
        request_dto.tenant_id = x_tenant_id

    buffer_bytes, metadata = await service.generate_report(request=request_dto, db=db)
    _report_cache[metadata.report_id] = (buffer_bytes, metadata)
    return SuccessResponse(data=metadata, metadata=_build_metadata(request_ctx))


@router.get(
    "/reports/history",
    response_model=SuccessResponse[list[ReportMetadataDTO]],
    status_code=status.HTTP_200_OK,
    summary="List recently generated enterprise reports",
)
async def list_generated_reports(
    request_ctx: Request,
    auth: AnalyticsAuth,
) -> SuccessResponse[list[ReportMetadataDTO]]:
    """Return metadata for all recently generated audit and compliance reports."""
    reports = [meta for _, meta in _report_cache.values()]
    reports.sort(key=lambda r: r.generated_at, reverse=True)
    return SuccessResponse(data=reports, metadata=_build_metadata(request_ctx))


@router.get(
    "/reports/download/{report_id}",
    status_code=status.HTTP_200_OK,
    summary="Download a generated report binary file",
)
async def download_generated_report(
    report_id: str,
    auth: AnalyticsAuth,
):
    """Download the generated PDF or JSON report file."""
    if report_id not in _report_cache:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found or expired.")

    buffer_bytes, metadata = _report_cache[report_id]
    media_type = "application/pdf" if metadata.report_type != "json" else "application/json"
    ext = "pdf" if metadata.report_type != "json" else "json"
    filename = f"RAGuard_{metadata.report_type}_{report_id}.{ext}"

    return Response(
        content=buffer_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


