import uuid
from typing import List, Any
from datetime import datetime
from pydantic import BaseModel, HttpUrl, ConfigDict, Field

class WorkspaceWebhookCreateDTO(BaseModel):
    endpoint_url: HttpUrl
    events: List[str]
    is_active: bool = True

class WorkspaceWebhookUpdateDTO(BaseModel):
    endpoint_url: HttpUrl | None = None
    events: List[str] | None = None
    is_active: bool | None = None

class WorkspaceWebhookResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    endpoint_url: str
    events: List[str]
    is_active: bool
    created_at: datetime

class WorkspaceWebhookSecretResponseDTO(BaseModel):
    id: uuid.UUID
    secret: str

class WebhookDeliveryLogDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    target: str
    status: str
    attempt_count: int
    error_message: str | None = None
    created_at: datetime
    event_type: str | None = None
    payload_summary: dict[str, Any] | None = None

class WebhookDeliveryLogsResponseDTO(BaseModel):
    items: List[WebhookDeliveryLogDTO]
    total: int
    limit: int
    offset: int

class WebhookEventCategoryDTO(BaseModel):
    category: str
    events: List[dict[str, str]]

class WebhookTestDispatchResponseDTO(BaseModel):
    status: str
    message: str
    event: str
