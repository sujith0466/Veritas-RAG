from sqlalchemy import Column, String, Float, Boolean, JSON, DateTime
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime, timezone
from backend.database.base import Base

class ScoringLogORM(Base):
    __tablename__ = "scoring_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    correlation_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    final_score = Column(Float, nullable=False)
    is_trusted = Column(Boolean, nullable=False)
    metadata_payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
