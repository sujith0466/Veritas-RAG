"""Processing Job Schemas.

Pydantic schemas for the job pipeline endpoints.
"""

from datetime import datetime
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class JobStepBase(BaseModel):
    step_name: str
    step_status: str
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: float | None = None
    error_code: str | None = None
    error_detail: dict[str, Any] | None = None


class JobStepResponse(JobStepBase):
    id: uuid.UUID
    job_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)


class JobAuditBase(BaseModel):
    event: str
    timestamp: datetime
    actor: str
    payload: dict[str, Any] | None = None


class JobAuditResponse(JobAuditBase):
    id: uuid.UUID
    job_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)


class ProcessingJobBase(BaseModel):
    document_id: uuid.UUID
    batch_id: uuid.UUID | None = None
    version_id: uuid.UUID | None = None
    status: str
    current_step: str
    priority: int = 1
    retry_count: int = 0
    max_retries: int = 3
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None
    step_metrics: dict[str, Any] | None = None


class ProcessingJobResponse(ProcessingJobBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    dlq_reason: str | None = None
    dlq_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ProcessingJobDetailResponse(ProcessingJobResponse):
    steps: list[JobStepResponse] = Field(default_factory=list)
    audits: list[JobAuditResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class RetryJobRequest(BaseModel):
    resume_from_step: str | None = None
