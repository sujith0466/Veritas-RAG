from pydantic import BaseModel, HttpUrl, ConfigDict
import uuid
from typing import List

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

class WorkspaceWebhookSecretResponseDTO(BaseModel):
    id: uuid.UUID
    secret: str
