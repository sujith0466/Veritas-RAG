"""Reporting DTO schemas for Enterprise Reporting Center."""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ReportType(str, Enum):
    """Supported enterprise report types."""
    SLA_COMPLIANCE = "sla_compliance"
    RELIABILITY_AUDIT = "reliability_audit"
    KNOWLEDGE_HEALTH = "knowledge_health"
    EXECUTIVE_SUMMARY = "executive_summary"


class ReportFormat(str, Enum):
    """Supported report export formats."""
    PDF = "pdf"
    JSON = "json"


class ReportExportRequestDTO(BaseModel):
    """Request DTO for generating an enterprise report."""
    report_type: ReportType = Field(..., description="Type of report to generate")
    start_date: Optional[datetime] = Field(None, description="Start date filter (UTC)")
    end_date: Optional[datetime] = Field(None, description="End date filter (UTC)")
    tenant_id: Optional[str] = Field("default", description="Tenant ID namespace")
    include_stage_breakdown: bool = Field(True, description="Whether to include stage latency/reliability breakdown")
    include_anomalies: bool = Field(True, description="Whether to include recent query anomaly details")
    format: ReportFormat = Field(ReportFormat.PDF, description="Output format (PDF or JSON)")


class ReportMetadataDTO(BaseModel):
    """Metadata DTO summarizing a generated report."""
    report_id: str = Field(..., description="Unique report ID")
    report_type: str = Field(..., description="Report type identifier")
    title: str = Field(..., description="Human-readable report title")
    generated_at: datetime = Field(..., description="Timestamp of generation")
    date_range_label: str = Field(..., description="Human-readable date range string")
    status: str = Field("READY", description="Report status (READY, FAILED)")
    download_url: str = Field(..., description="URL endpoint to download the report file")
    summary_metrics: Dict[str, Any] = Field(default_factory=dict, description="Key metrics included in report summary")
