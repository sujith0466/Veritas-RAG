from datetime import UTC, datetime
import uuid

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, String
from sqlalchemy.dialects.postgresql import UUID

from backend.database.base import Base


class ScoringLogORM(Base):
    __tablename__ = "scoring_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    correlation_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    final_score = Column(Float, nullable=False)
    is_trusted = Column(Boolean, nullable=False)
    metadata_payload = Column(JSON, nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
