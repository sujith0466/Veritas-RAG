from sqlalchemy import Column, String, Integer, Boolean, JSON
from backend.models.base import BaseModel

class Policy(BaseModel):
    __tablename__ = "policies"
    tenant_id = Column(String, nullable=False, index=True)
    workspace_id = Column(String, nullable=True, index=True)
    max_tokens = Column(Integer, nullable=True)
    blocked_topics = Column(JSON, nullable=True)
    redact_pii = Column(Boolean, nullable=True)
    block_jailbreaks = Column(Boolean, nullable=True)

class PolicyViolationAudit(BaseModel):
    __tablename__ = "policy_violation_audits"
    tenant_id = Column(String, nullable=False, index=True)
    workspace_id = Column(String, nullable=False, index=True)
    query = Column(String, nullable=False)
    violation_type = Column(String, nullable=False)
    action_taken = Column(String, nullable=False)
