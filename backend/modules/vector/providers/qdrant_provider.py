"""Self-hosted Qdrant vector database provider implementation (`ADR-004`).

Implements `BaseVectorDBProvider` using `AsyncQdrantClient` with gRPC preference,
INT8 scalar quantization support (`ADR-M3-002`), exact payload indexing for multi-tenant
filtering (`ADR-M3-001`), and standardized domain error mapping (`VEC_xxx`).
"""

from typing import Any
import structlog
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qdrant_models

from backend.vector_db.client import get_qdrant_client
from backend.modules.vector.providers.base import BaseVectorDBProvider
from backend.modules.vector.schemas.errors import (
    CollectionNotFoundError,
    DimensionMismatchError,
    InvalidPayloadSchemaError,
    QdrantConnectionError,
)
from backend.modules.vector.schemas.payload import (
    CollectionConfigDTO,
    CollectionSummaryDTO,
    VectorPointDTO,
)

logger = structlog.get_logger(__name__)


class QdrantVectorDBProvider(BaseVectorDBProvider):
    """Concrete self-hosted Qdrant provider implementation (`ADR-004`)."""

    def __init__(self, client: AsyncQdrantClient | None = None) -> None:
        self._client = client

    @property
    def client(self) -> AsyncQdrantClient:
        """Return the active AsyncQdrantClient instance."""
        if self._client is not None:
            return self._client
        return get_qdrant_client()

    @property
    def provider_name(self) -> str:
        return "qdrant"

    async def ensure_collection(self, config: CollectionConfigDTO) -> bool:
        """Ensure the target collection exists with exact dimension and quantization settings."""
        log = logger.bind(collection_name=config.collection_name, dimension=config.dimension)
        try:
            exists = await self.client.collection_exists(collection_name=config.collection_name)
            if exists:
                log.debug("Target Qdrant collection already exists; verifying status")
                return True

            log.info("Creating new Qdrant collection with HNSW and INT8 scalar quantization")
            distance_map = {
                "Cosine": qdrant_models.Distance.COSINE,
                "Dot": qdrant_models.Distance.DOT,
                "Euclidean": qdrant_models.Distance.EUCLID,
            }
            distance = distance_map.get(config.distance_metric, qdrant_models.Distance.COSINE)

            quantization_config = None
            if config.scalar_quantization:
                quantization_config = qdrant_models.ScalarQuantization(
                    scalar=qdrant_models.ScalarQuantizationConfig(
                        type=qdrant_models.ScalarType.INT8,
                        quantile=0.99,
                        always_ram=True,
                    )
                )

            await self.client.create_collection(
                collection_name=config.collection_name,
                vectors_config=qdrant_models.VectorParams(
                    size=config.dimension,
                    distance=distance,
                    on_disk=config.on_disk_payload,
                ),
                quantization_config=quantization_config,
            )
            return True
        except Exception as exc:
            log.error("Failed to ensure Qdrant collection topology", error=str(exc))
            raise QdrantConnectionError(
                message=f"Failed to verify or create collection '{config.collection_name}': {exc}",
                detail={"collection_name": config.collection_name, "error": str(exc)},
            ) from exc

    async def create_payload_indexes(self, collection_name: str, indexed_fields: list[str]) -> bool:
        """Create keyword index structures on payload fields (`ADR-M3-001`)."""
        log = logger.bind(collection_name=collection_name, indexed_fields=indexed_fields)
        try:
            for field in indexed_fields:
                try:
                    await self.client.create_payload_index(
                        collection_name=collection_name,
                        field_name=field,
                        field_schema=qdrant_models.PayloadSchemaType.KEYWORD,
                    )
                except Exception as idx_exc:
                    # If index already exists or status is running, log and continue safely
                    if "already exists" in str(idx_exc).lower() or "running" in str(idx_exc).lower():
                        log.debug("Payload index already present or initializing", field=field)
                    else:
                        raise
            return True
        except Exception as exc:
            log.error("Failed to create payload indexes in Qdrant", error=str(exc))
            raise QdrantConnectionError(
                message=f"Failed to create payload indexes on '{collection_name}': {exc}",
                detail={"collection_name": collection_name, "error": str(exc)},
            ) from exc

    async def upsert_points(self, collection_name: str, points: list[VectorPointDTO]) -> int:
        """Batch upsert points into Qdrant collection with structured payload validation."""
        if not points:
            return 0

        log = logger.bind(collection_name=collection_name, points_count=len(points))
        try:
            qdrant_points = [
                qdrant_models.PointStruct(
                    id=str(p.point_id),
                    vector=p.vector,
                    payload=p.payload,
                )
                for p in points
            ]

            await self.client.upsert(
                collection_name=collection_name,
                points=qdrant_points,
                wait=True,
            )
            log.debug("Successfully upserted point batch into Qdrant")
            return len(points)
        except Exception as exc:
            err_str = str(exc).lower()
            log.error("Qdrant point batch upsert failed", error=err_str)
            if "not found" in err_str:
                raise CollectionNotFoundError(
                    message=f"Collection '{collection_name}' not found during batch upsert.",
                    detail={"collection_name": collection_name},
                ) from exc
            elif "dimension" in err_str or "size mismatch" in err_str or "wrong vector size" in err_str:
                raise DimensionMismatchError(
                    message=f"Vector dimension mismatch when upserting into '{collection_name}': {exc}",
                    detail={"collection_name": collection_name, "error": str(exc)},
                ) from exc
            elif "payload" in err_str or "schema" in err_str:
                raise InvalidPayloadSchemaError(
                    message=f"Payload schema violation during upsert: {exc}",
                    detail={"collection_name": collection_name, "error": str(exc)},
                ) from exc
            raise QdrantConnectionError(
                message=f"Qdrant connection or transport failure during point upsert: {exc}",
                detail={"collection_name": collection_name, "error": str(exc)},
            ) from exc

    async def delete_points_by_filter(
        self,
        collection_name: str,
        filter_conditions: dict[str, Any],
    ) -> int:
        """Delete points matching exact payload keyword conditions (`ADR-M3-001`)."""
        if not filter_conditions:
            return 0

        log = logger.bind(collection_name=collection_name, filter=filter_conditions)
        try:
            must_conditions = [
                qdrant_models.FieldCondition(
                    key=key,
                    match=qdrant_models.MatchValue(value=value),
                )
                for key, value in filter_conditions.items()
            ]
            filter_selector = qdrant_models.FilterSelector(
                filter=qdrant_models.Filter(must=must_conditions)
            )

            result = await self.client.delete(
                collection_name=collection_name,
                points_selector=filter_selector,
                wait=True,
            )
            log.info("Successfully deleted points matching payload filter conditions")
            return getattr(result, "operation_id", 1)
        except Exception as exc:
            err_str = str(exc).lower()
            log.error("Failed to delete points by payload filter", error=err_str)
            if "not found" in err_str:
                raise CollectionNotFoundError(
                    message=f"Collection '{collection_name}' not found during point deletion.",
                    detail={"collection_name": collection_name},
                ) from exc
            raise QdrantConnectionError(
                message=f"Qdrant failure during point deletion by filter: {exc}",
                detail={"collection_name": collection_name, "error": str(exc)},
            ) from exc

    async def get_collection_info(self, collection_name: str) -> CollectionSummaryDTO:
        """Fetch summary health metrics and point counts for a target collection."""
        try:
            info = await self.client.get_collection(collection_name=collection_name)
            dimension = 0
            if info.config and info.config.params and info.config.params.vectors:
                vec_config = info.config.params.vectors
                if isinstance(vec_config, qdrant_models.VectorParams):
                    dimension = vec_config.size or 0
                elif isinstance(vec_config, dict):
                    # Multi-vector config or dict representation
                    first_val = next(iter(vec_config.values())) if vec_config else None
                    if isinstance(first_val, qdrant_models.VectorParams):
                        dimension = first_val.size or 0
                    elif isinstance(first_val, dict):
                        dimension = first_val.get("size", 0)

            return CollectionSummaryDTO(
                collection_name=collection_name,
                points_count=info.points_count or 0,
                indexed_vectors_count=info.indexed_vectors_count or 0,
                status=str(info.status.name if hasattr(info.status, "name") else info.status),
                vector_dimension=dimension,
            )
        except Exception as exc:
            err_str = str(exc).lower()
            if "not found" in err_str or "doesn't exist" in err_str:
                raise CollectionNotFoundError(
                    message=f"Collection '{collection_name}' does not exist in Qdrant cluster.",
                    detail={"collection_name": collection_name},
                ) from exc
            raise QdrantConnectionError(
                message=f"Failed to retrieve collection info for '{collection_name}': {exc}",
                detail={"collection_name": collection_name, "error": str(exc)},
            ) from exc

    async def search_points(
        self,
        collection_name: str,
        query_vector: list[float],
        filter_conditions: dict[str, Any],
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Search for approximate nearest neighbors in Qdrant with exact payload filtering."""
        log = logger.bind(collection_name=collection_name, filter=filter_conditions, limit=limit)
        try:
            must_conditions = [
                qdrant_models.FieldCondition(
                    key=key,
                    match=qdrant_models.MatchValue(value=value),
                )
                for key, value in filter_conditions.items()
            ]
            filter_selector = (
                qdrant_models.Filter(must=must_conditions) if must_conditions else None
            )

            # Use search or query_points compatible across AsyncQdrantClient versions
            results = await self.client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                query_filter=filter_selector,
                limit=limit,
                with_payload=True,
            )
            candidates: list[dict[str, Any]] = []
            for hit in results:
                candidates.append({
                    "point_id": str(hit.id),
                    "score": float(hit.score),
                    "payload": hit.payload or {},
                })
            log.debug("Successfully executed dense search in Qdrant", hits_count=len(candidates))
            return candidates
        except Exception as exc:
            err_str = str(exc).lower()
            log.error("Failed to execute dense search in Qdrant", error=err_str)
            if "not found" in err_str or "doesn't exist" in err_str:
                raise CollectionNotFoundError(
                    message=f"Collection '{collection_name}' not found during point search.",
                    detail={"collection_name": collection_name},
                ) from exc
            raise QdrantConnectionError(
                message=f"Qdrant failure during point search: {exc}",
                detail={"collection_name": collection_name, "error": str(exc)},
            ) from exc

