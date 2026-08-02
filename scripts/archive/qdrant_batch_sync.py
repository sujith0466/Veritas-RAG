import asyncio
import os
import sys

import httpx
from sqlalchemy import select
import structlog

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.core.config.qdrant import QdrantSettings
from backend.database.engine import get_session_factory
from backend.modules.embedding.models.chunk_embedding import ChunkEmbedding

logger = structlog.get_logger(__name__)

async def qdrant_batch_sync():
    qdrant_settings = QdrantSettings()
    session_factory = get_session_factory()
    collection_name = "raguard_knowledge_384"

    url = f"http://{qdrant_settings.host}:{qdrant_settings.port}"

    # Check if collection exists
    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(f"{url}/collections/{collection_name}")
            if res.status_code == 404:
                logger.info(f"Creating collection {collection_name}")
                await client.put(f"{url}/collections/{collection_name}", json={
                    "vectors": {
                        "size": 384,
                        "distance": "Cosine"
                    }
                })
        except Exception as e:
            logger.error(f"Error checking collection: {e}")

    async with session_factory() as session:
        # Get all embeddings
        stmt = select(ChunkEmbedding)
        embeddings = (await session.execute(stmt)).scalars().all()
        logger.info(f"Found {len(embeddings)} embeddings to sync")

        batch_size = 500
        async with httpx.AsyncClient(timeout=30.0) as client:
            for i in range(0, len(embeddings), batch_size):
                batch = embeddings[i:i+batch_size]

                points = []
                for emb in batch:
                    points.append({
                        "id": str(emb.chunk_id),
                        "vector": emb.embedding_vector,
                        "payload": {
                            "document_id": str(emb.document.id) if getattr(emb, "document", None) else None, # We don't have document joined, but we can query it or just skip
                            "tenant_id": emb.tenant_id,
                            "chunk_id": str(emb.chunk_id),
                            "document_version_id": str(emb.document_version_id)
                        }
                    })

                # Fix payload document_id using another query if needed, but VectorService just puts tenant_id, chunk_id, document_version_id, document_id.
                # Since DocumentChunk has document_id, let's just get it.

                res = await client.put(f"{url}/collections/{collection_name}/points?wait=true", json={"points": points})
                if res.status_code != 200:
                    logger.error(f"Failed to upsert batch {i}: {res.text}")
                else:
                    logger.info(f"Upserted batch {i} to {i+len(batch)}")

if __name__ == "__main__":
    asyncio.run(qdrant_batch_sync())
