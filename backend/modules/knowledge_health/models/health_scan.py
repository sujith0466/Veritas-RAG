"""ORM entity representing scheduled or manual health scan audit jobs (`health_scan_jobs`)."""

from datetime import UTC, datetime
import uuid

from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from backend.database.base import Base


class HealthScanJob(Base):
    """ORM table for logging health scan statistics, parity checks, and orphan cleanup records."""

    __tablename__ = "health_scan_jobs"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String(100), nullable=False, index=True)
    scan_type = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False, default="PENDING")
    orphans_found = Column(Integer, nullable=False, default=0)
    orphans_purged = Column(Integer, nullable=False, default=0)
    stale_chunks_found = Column(Integer, nullable=False, default=0)
    parity_status = Column(String(100), nullable=False, default="UNKNOWN")
    duration_ms = Column(Float, nullable=False, default=0.0)
    error_message = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return f"<HealthScanJob(id={self.id}, tenant_id='{self.tenant_id}', scan_type='{self.scan_type}', status='{self.status}')>"
