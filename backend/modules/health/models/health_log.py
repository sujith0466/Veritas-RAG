from sqlalchemy import Column, String, Float, JSON, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime, timezone
from backend.database.base import Base

class HealthLogORM(Base):
    __tablename__ = "health_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String(64), nullable=False, index=True)
    health_score = Column(Float, nullable=False)
    issues_found_count = Column(Integer, nullable=False)
    metadata_payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

class QuarantineLogORM(Base):
    __tablename__ = "quarantine_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(String(128), nullable=False, index=True)
    action = Column(String(32), nullable=False)
    reason = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
