"""Unit tests for Enterprise Reporting Center (`ReportingService` & endpoints)."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.modules.analytics.api.routes import (
    download_generated_report,
    export_enterprise_report,
    list_generated_reports,
)
from backend.modules.analytics.schemas.analytics_dto import (
    ConfidenceAnalyticsDTO,
    LatencyAnalyticsDTO,
    SuccessRateDTO,
)
from backend.modules.analytics.schemas.reporting_dto import (
    ReportExportRequestDTO,
    ReportFormat,
    ReportType,
)
from backend.modules.analytics.services.reporting_service import ReportingService


@pytest.fixture
def mock_analytics_service():
    service = MagicMock()
    service.get_success_rate = AsyncMock(return_value=SuccessRateDTO(
        total_queries=1250,
        success_count=1240,
        clarification_count=8,
        failure_count=2,
        retry_count=15,
        success_rate_percentage=99.2,
        avg_retries_per_query=0.012,
    ))
    service.get_latency_analytics = AsyncMock(return_value=LatencyAnalyticsDTO(
        p50_ms=280.0,
        p90_ms=620.0,
        p95_ms=890.0,
        p99_ms=1340.0,
        avg_ms=342.5,
    ))
    service.get_confidence_analytics = AsyncMock(return_value=ConfidenceAnalyticsDTO(
        avg_confidence=0.884,
        min_confidence=0.35,
        max_confidence=0.99,
        high_confidence_count=1100,
        medium_confidence_count=135,
        low_confidence_count=15,
    ))
    return service


@pytest.mark.asyncio
async def test_generate_sla_compliance_pdf(mock_analytics_service):
    service = ReportingService(mock_analytics_service)
    request = ReportExportRequestDTO(
        report_type=ReportType.SLA_COMPLIANCE,
        tenant_id="enterprise_tenant",
        include_stage_breakdown=True,
        include_anomalies=True,
        format=ReportFormat.PDF,
    )

    mock_db = AsyncMock()
    pdf_bytes, metadata = await service.generate_report(request, mock_db)

    assert len(pdf_bytes) > 500
    assert pdf_bytes.startswith(b"%PDF-")
    assert metadata.report_type == "sla_compliance"
    assert metadata.title == "Enterprise SLA Compliance & Performance Report"
    assert metadata.summary_metrics["total_queries"] == 1250
    assert metadata.summary_metrics["success_rate"] == 99.2
    assert metadata.summary_metrics["p95_latency_ms"] == 890.0


@pytest.mark.asyncio
async def test_generate_reliability_audit_json(mock_analytics_service):
    service = ReportingService(mock_analytics_service)
    request = ReportExportRequestDTO(
        report_type=ReportType.RELIABILITY_AUDIT,
        format=ReportFormat.JSON,
    )

    mock_db = AsyncMock()
    json_bytes, metadata = await service.generate_report(request, mock_db)

    data = json.loads(json_bytes.decode("utf-8"))
    assert data["report_type"] == "reliability_audit"
    assert data["metrics"]["hallucination_rate"] == 1.2
    assert metadata.status == "READY"


@pytest.mark.asyncio
async def test_reporting_endpoints(mock_analytics_service):
    service = ReportingService(mock_analytics_service)
    request_dto = ReportExportRequestDTO(
        report_type=ReportType.KNOWLEDGE_HEALTH,
        format=ReportFormat.PDF,
    )
    mock_req = MagicMock()
    mock_req.state.correlation_id = "test-corr-id"
    mock_db = AsyncMock()
    auth = MagicMock()
    auth.role = "analyst"
    auth.tenant_id = "tenant_123"

    # 1. Export Report
    export_res = await export_enterprise_report(
        request_dto=request_dto,
        request_ctx=mock_req,
        service=service,
        db=mock_db,
        auth=auth,
        x_tenant_id="tenant_123",
    )
    assert export_res.data.report_type == "knowledge_health"
    report_id = export_res.data.report_id

    # 2. List Reports
    list_res = await list_generated_reports(
        request_ctx=mock_req,
        auth=auth,
    )
    assert any(r.report_id == report_id for r in list_res.data)

    # 3. Download Report
    download_res = await download_generated_report(report_id=report_id, auth=auth)
    assert download_res.media_type == "application/pdf"
    assert download_res.body.startswith(b"%PDF-")
