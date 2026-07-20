from pydantic import BaseModel, Field
from enum import StrEnum

class IssueType(StrEnum):
    REDUNDANT = "REDUNDANT"
    CONTRADICTORY = "CONTRADICTORY"
    LOW_USAGE = "LOW_USAGE"
    OUTDATED = "OUTDATED"

class QuarantineAction(StrEnum):
    FLAG = "FLAG"
    SOFT_DELETE = "SOFT_DELETE"
    ARCHIVE = "ARCHIVE"

class DocumentIssueDTO(BaseModel):
    document_id: str = Field(...)
    issue_type: IssueType = Field(...)
    description: str = Field(...)
    severity: float = Field(..., ge=0.0, le=1.0)
    related_document_ids: list[str] = Field(default_factory=list)

class QuarantineRequestDTO(BaseModel):
    document_id: str = Field(...)
    action: QuarantineAction = Field(...)
    reason: str = Field(...)

class HealthReportDTO(BaseModel):
    tenant_id: str = Field(...)
    total_documents_analyzed: int = Field(...)
    issues_found: list[DocumentIssueDTO] = Field(default_factory=list)
    quarantined_documents: list[str] = Field(default_factory=list)
    health_score: float = Field(..., ge=0.0, le=100.0)
