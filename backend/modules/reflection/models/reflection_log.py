from sqlalchemy import Column, String, Float, Boolean, JSON, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime, timezone
from backend.database.base import Base

class ReflectionLogORM(Base):
    __tablename__ = "reflection_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    correlation_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    overall_verdict = Column(String(32), nullable=False)
    hallucination_score = Column(Float, nullable=False)
    completeness_score = Column(Float, nullable=False)
    consistency_score = Column(Float, nullable=False)
    is_safe_to_serve = Column(Boolean, nullable=False)
    attempt_number = Column(Integer, nullable=False, default=1)
    metadata_payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
