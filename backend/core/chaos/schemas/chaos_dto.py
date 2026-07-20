from pydantic import BaseModel
from typing import Optional

class FaultPolicyCreateDTO(BaseModel):
    chaos_token: str
    fault_type: str
    target_provider: Optional[str] = None
    latency_ms: int = 0
    error_rate_pct: float = 1.0
    is_active: bool = True

class FaultPolicyDTO(FaultPolicyCreateDTO):
    id: str
    expires_at: str

class FailoverCommandDTO(BaseModel):
    target_region: str
    force: bool = False

class FailoverStatusDTO(BaseModel):
    status: str
    active_region: str
    message: str
