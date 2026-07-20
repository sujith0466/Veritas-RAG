from pydantic import BaseModel
from typing import List

class DLPRedactionResultDTO(BaseModel):
    original_text: str
    redacted_text: str
    entities_redacted: int
    redaction_types: List[str]

class AuditEventDTO(BaseModel):
    tenant_id: str
    actor_id: str
    action: str
    resource: str
    status: str
    timestamp: str
    ip_address: str | None = None
