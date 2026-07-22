"""Abstract base provider interface for vector database storage (`ADR-004`).

Ensures vector storage operations remain independent of the underlying database engine,
allowing clean testing mocks and future extensibility while enforcing multi-tenant boundaries.
"""

from abc import ABC, abstractmethod
from typing import Any

from backend.modules.vector.schemas.payload import (CollectionConfigDTO,
                                                    CollectionSummaryDTO,
                                                    VectorPointDTO)


class BaseVectorDBProvider(ABC):
    """Abstract base class for vector database providers (`ADR-004`)."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the unique identifier string of the provider (e.g., 'qdrant')."""

    @abstractmethod
    async def ensure_collection(self, config: CollectionConfigDTO) -> bool:
        """Ensure the target collection exists with the specified dimension and quantization settings.

        Args:
            config: Collection specification including name, dimension, and quantization options.

        Returns:
            True if collection was created or verified existing without error.
        """

    @abstractmethod
    async def create_payload_indexes(
        self, collection_name: str, indexed_fields: list[str]
    ) -> bool:
        """Create exact keyword payload index structures for instantaneous multi-tenant filtering.

        Args:
            collection_name: Target collection name.
            indexed_fields: List of payload property names to index (e.g., ['tenant_id', 'document_id']).

        Returns:
            True if indexes were successfully configured.
        """

    @abstractmethod
    async def upsert_points(
        self, collection_name: str, points: list[VectorPointDTO]
    ) -> int:
        """Batch upsert vector points into the target collection.

        Args:
            collection_name: Target collection name.
            points: List of validated `VectorPointDTO` items containing point IDs, vectors, and payloads.

        Returns:
            Number of points successfully upserted.
        """

    @abstractmethod
    async def delete_points_by_filter(
        self,
        collection_name: str,
        filter_conditions: dict[str, Any],
    ) -> int:
        """Delete vector points matching the specified payload filter conditions.

        Args:
            collection_name: Target collection name.
            filter_conditions: Dictionary of exact payload equality matches (e.g., {'tenant_id': '...', 'document_id': '...'}).

        Returns:
            Number of points deleted or operation status count.
        """

    @abstractmethod
    async def get_collection_info(self, collection_name: str) -> CollectionSummaryDTO:
        """Fetch summary health metrics and point counts for a target collection.

        Args:
            collection_name: Target collection name.

        Returns:
            CollectionSummaryDTO containing point counts, status, and dimensions.
        """

    @abstractmethod
    async def search_points(
        self,
        collection_name: str,
        query_vector: list[float],
        filter_conditions: dict[str, Any],
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Search for approximate nearest neighbors matching the query vector and exact payload filters.

        Args:
            collection_name: Target collection name.
            query_vector: Dense query embedding vector (`float list`).
            filter_conditions: Exact payload equality matches for tenant isolation (e.g., {'tenant_id': '...'}).
            limit: Maximum number of candidate points to retrieve.

        Returns:
            List of dictionaries containing 'point_id', 'score', and 'payload'.
        """
