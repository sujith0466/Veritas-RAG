from sqlalchemy import Column, String, Float, Boolean, JSON, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime, timezone
from backend.database.base import Base

class ValidationLogORM(Base):
    __tablename__ = "validation_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    correlation_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    overall_verdict = Column(String(32), nullable=False)
    entailment_ratio = Column(Float, nullable=False)
    unsupported_claim_count = Column(Integer, nullable=False)
    invalid_citation_count = Column(Integer, nullable=False)
    is_valid = Column(Boolean, nullable=False)
    metadata_payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
