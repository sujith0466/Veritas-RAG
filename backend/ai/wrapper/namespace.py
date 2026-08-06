import uuid

from qdrant_client.http.exceptions import UnexpectedResponse
from redis.asyncio import Redis
import structlog

from backend.ai.schemas.wrapper_dto import NamespaceBinding
from backend.cache.client import get_redis_client
from backend.vector_db.client import get_qdrant_client

logger = structlog.get_logger(__name__)


class NamespaceResolver:
    """Resolves and caches the 1:1 binding between Tenant/Workspace and Qdrant Collection."""

    def __init__(self) -> None:
        self.redis: Redis = get_redis_client()
        self.qdrant = get_qdrant_client()

    async def resolve(self, workspace_id: uuid.UUID, tenant_id: uuid.UUID) -> NamespaceBinding:
        """
        Resolve the Qdrant namespace (collection) for a given workspace/tenant.
        Uses Redis cache for 300s TTL.
        """
        cache_key = f"raguard:{tenant_id}:namespace:binding"

        # 1. Check Cache
        cached_collection = await self.redis.get(cache_key)
        if cached_collection:
            logger.debug("Namespace cache hit", tenant_id=str(tenant_id), collection=cached_collection)
            return NamespaceBinding(
                workspace_id=workspace_id,
                tenant_id=tenant_id,
                collection_name=cached_collection
            )

        # 2. Construct canonical collection name (1:1 mapping as per Q3 Option A)
        collection_name = f"raguard_knowledge_{tenant_id}"

        # 3. Validate existence via Qdrant ping
        try:
            # We use collection_info instead of get_collections to specifically target
            await self.qdrant.get_collection(collection_name=collection_name)
        except UnexpectedResponse as e:
            if e.status_code == 404:
                logger.warning("Namespace collection not found in Qdrant", collection=collection_name)
                # We do not fail hard here, as RetrievalOrchestrator handles empty/missing gracefully,
                # but we still log it.
            else:
                logger.error("Unexpected Qdrant error during namespace resolution", error=str(e))
                raise

        # 4. Cache and Return
        await self.redis.setex(cache_key, 300, collection_name)
        logger.debug("Namespace cache populated", tenant_id=str(tenant_id), collection=collection_name)

        return NamespaceBinding(
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            collection_name=collection_name
        )
