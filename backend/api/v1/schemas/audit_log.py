from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditLogDTO(BaseModel):
    """Data Transfer Object representing an Audit Log entry."""

    id: UUID
    tenant_id: UUID | None = None
    user_id: UUID | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    details: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
