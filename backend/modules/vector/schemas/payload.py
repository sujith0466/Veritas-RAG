"""Payload and schema DTOs for the Vector Storage Foundation (`ADR-M3-001`).

Enforces strict payload structure requirements (`tenant_id`, `document_id`,
`document_version_id`, `content_hash`) to guarantee multi-tenant isolation
and instantaneous indexed payload filtering inside Qdrant.
"""

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class VectorPointDTO(BaseModel):
    """Represents a single vector point to be upserted into Qdrant."""

    point_id: str | uuid.UUID = Field(
        ..., description="Deterministic point ID (UUIDv5 from content hash)"
    )
    vector: list[float] = Field(..., description="Dense float vector array")
    payload: dict[str, Any] = Field(
        ...,
        description="Structured metadata payload containing mandatory tenant and document identifiers",
    )

    model_config = ConfigDict(from_attributes=True)

    @field_validator("point_id", mode="before")
    @classmethod
    def format_point_id(cls, v: Any) -> str:
        return str(v)

    @field_validator("payload")
    @classmethod
    def validate_mandatory_payload_keys(cls, v: dict[str, Any]) -> dict[str, Any]:
        required_keys = {
            "tenant_id",
            "document_id",
            "document_version_id",
            "content_hash",
        }
        missing = required_keys - v.keys()
        if missing:
            raise ValueError(
                f"Vector payload missing mandatory multi-tenant keys: {missing}"
            )
        return v


class CollectionConfigDTO(BaseModel):
    """Configuration specifications for creating or verifying a Qdrant collection (`ADR-M3-001`)."""

    collection_name: str = Field(
        ..., description="Target Qdrant collection name (e.g., raguard_knowledge_1536)"
    )
    dimension: int = Field(..., gt=0, description="Vector dimension size")
    distance_metric: str = Field(
        "Cosine", description="Vector distance metric (Cosine, Dot, or Euclidean)"
    )
    on_disk_payload: bool = Field(
        True, description="Whether payloads are stored on disk to preserve RAM"
    )
    scalar_quantization: bool = Field(
        True, description="Whether INT8 scalar quantization is enabled (`ADR-M3-002`)"
    )

    model_config = ConfigDict(from_attributes=True)


class CollectionSummaryDTO(BaseModel):
    """Summary metrics and health status of a Qdrant vector collection."""

    collection_name: str
    points_count: int
    indexed_vectors_count: int
    status: str
    vector_dimension: int
    on_disk_payload: bool = True

    model_config = ConfigDict(from_attributes=True)


class VectorBatchRequestDTO(BaseModel):
    """Request payload for batch point upsert operations."""

    document_id: str | uuid.UUID
    document_version_id: str | uuid.UUID
    tenant_id: str | uuid.UUID
    points: list[VectorPointDTO] = Field(
        ..., description="Batch of vector points with payloads"
    )

    model_config = ConfigDict(from_attributes=True)

    @field_validator("document_id", "document_version_id", "tenant_id", mode="before")
    @classmethod
    def format_uuid_fields(cls, v: Any) -> str:
        return str(v)


class VectorSyncRequestDTO(BaseModel):
    """Request DTO to trigger asynchronous vector synchronization for a document version (`ADR-M3-001`)."""

    document_id: uuid.UUID = Field(..., description="UUID of the parent document")
    collection_name: str | None = Field(
        None, description="Optional target collection override"
    )

    model_config = ConfigDict(from_attributes=True)


class VectorIndexMetadataDTO(BaseModel):
    """API DTO representing the synchronization status and metadata of a document version in Qdrant."""

    id: uuid.UUID
    tenant_id: str
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    collection_name: str
    status: str
    points_count: int
    error_message: str | None = None

    model_config = ConfigDict(from_attributes=True)


class CollectionDetailDTO(BaseModel):
    """Summary metrics for an active tenant vector collection."""

    collection_name: str
    total_points: int
    indexed_versions_count: int

    model_config = ConfigDict(from_attributes=True)


class QdrantClusterHealthDTO(BaseModel):
    """System cluster health summary across vector storage namespaces."""

    status: str
    active_collections_count: int
    total_points_stored: int
    collections: list[CollectionDetailDTO] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class PurgeSummaryDTO(BaseModel):
    """Summary response for document point deletion across collections (`ADR-M3-001`)."""

    document_id: uuid.UUID
    tenant_id: str
    purged_points_count: int

    model_config = ConfigDict(from_attributes=True)
