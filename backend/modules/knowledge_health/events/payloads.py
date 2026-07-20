"""Event payload definitions for Knowledge Health & Lifecycle (`schema v1.0.0`)."""

from dataclasses import dataclass
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import BaseModel, Field
from backend.core.events.base import BaseEvent
from backend.core.events.types import EventType


@dataclass(frozen=True)
class KnowledgeHealthDomainEvent(BaseEvent):
    """Event wrapper carrying Knowledge Health DTO payloads for distribution across the EventDispatcher bus."""

    payload: Optional[Dict[str, Any]] = None


class KnowledgeHealthScanStartedPayload(BaseModel):
    """Payload emitted when a scheduled or manual health scan begins."""

    job_id: UUID = Field(..., description="Scan job ID.")
    tenant_id: str = Field(..., description="Tenant namespace ID.")
    scan_type: str = Field(..., description="Type of scan initiated.")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()

    def get_event_type(self) -> EventType:
        return EventType.KNOWLEDGE_HEALTH_SCAN_STARTED


class KnowledgeHealthScanCompletedPayload(BaseModel):
    """Payload emitted when a health scan finishes successfully or fails."""

    job_id: UUID = Field(..., description="Scan job ID.")
    tenant_id: str = Field(..., description="Tenant namespace ID.")
    scan_type: str = Field(..., description="Executed scan type.")
    status: str = Field(..., description="Final job status.")
    orphans_purged: int = Field(default=0, description="Total orphaned items removed.")
    parity_status: str = Field(default="UNKNOWN", description="Count parity status string.")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()

    def get_event_type(self) -> EventType:
        return EventType.KNOWLEDGE_HEALTH_SCAN_COMPLETED


class OrphanChunksPurgedPayload(BaseModel):
    """Payload emitted when orphaned chunks or vector points are cleaned up."""

    tenant_id: str = Field(..., description="Tenant namespace ID.")
    document_id: Optional[UUID] = Field(default=None, description="Parent document ID if explicit purge.")
    chunks_purged: int = Field(..., description="Count of DB chunks purged.")
    vectors_purged: int = Field(..., description="Count of Qdrant points purged.")
    reason: str = Field(..., description="Trigger explanation (e.g. 'TWO_PHASE_PURGE', 'SCHEDULED_ORPHAN_SWEEP').")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()

    def get_event_type(self) -> EventType:
        return EventType.ORPHAN_CHUNKS_PURGED


class KnowledgeDriftDetectedPayload(BaseModel):
    """Payload emitted when model rotation or count parity discrepancies are detected."""

    tenant_id: str = Field(..., description="Tenant namespace ID.")
    drift_type: str = Field(..., description="Drift classification (`PARITY_MISMATCH` or `MODEL_ROTATION_STALE`).")
    details: Dict[str, Any] = Field(default_factory=dict, description="Drift metrics and counts.")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()

    def get_event_type(self) -> EventType:
        return EventType.KNOWLEDGE_DRIFT_DETECTED
