import asyncio

from qdrant_client import AsyncQdrantClient
from sqlalchemy import func, select

from backend.core.config import get_settings
from backend.database.engine import get_session_factory
from backend.document.models import Document
from backend.models.entities.user import User
from backend.modules.chunking.models import DocumentChunk
from backend.modules.embedding.models import ChunkEmbedding


async def run_audit():
    print("=== PHASE 3: Document Verification ===")
    session_maker = get_session_factory()
    async with session_maker() as session:
        doc_count = (await session.execute(select(func.count()).select_from(Document))).scalar()
        chunk_count = (await session.execute(select(func.count()).select_from(DocumentChunk))).scalar()
        embed_count = (await session.execute(select(func.count()).select_from(ChunkEmbedding))).scalar()

        print(f"Documents: {doc_count}")
        print(f"Chunks: {chunk_count}")
        print(f"Embeddings: {embed_count}")

    print("\n=== PHASE 4: Qdrant Audit ===")
    settings = get_settings()
    try:
        client = AsyncQdrantClient(host=settings.qdrant.host, port=settings.qdrant.port)
        collections = await client.get_collections()
        print(f"Collections: {collections}")
        if collections.collections:
            for c in collections.collections:
                info = await client.get_collection(c.name)
                print(f"Collection {c.name}: vectors={info.vectors_count}, status={info.status}")
                # Try a sample search
                res = await client.search(
                    collection_name=c.name,
                    query_vector=[0.0]*384, # assuming 384 dim for all-MiniLM
                    limit=1
                )
                print(f"Sample search results count: {len(res)}")
    except Exception as e:
        print(f"Qdrant Error: {e}")

    print("\n=== PHASE 5 & 6: Retrieval Debug ===")
    from backend.modules.retrieval.schemas.retrieval_dto import SearchRequestDTO
    from backend.modules.retrieval.services.retrieval_service import RetrievalOrchestrator

    # We need a tenant_id. Let's get demoadmin tenant_id
    async with session_maker() as session:
        admin = (await session.execute(select(User).where(User.email == "demoadmin@gmail.com"))).scalar_one_or_none()
        if not admin:
            print("No admin user found.")
            return
        tenant_id = admin.tenant_id

    orchestrator = RetrievalOrchestrator()
    search_req = SearchRequestDTO(query="What is our PTO policy?", top_k=5, rerank=True, semantic_weight=0.7)

    try:
        res = await orchestrator.execute_hybrid_search(search_req, tenant_id=tenant_id, correlation_id="test")
        print(f"Retrieval found {len(res.top_candidates)} chunks.")
        for c in res.top_candidates:
            print(f"Score: {c.score}, Chunk ID: {c.chunk_id}, Content Preview: {c.content[:50]}")
    except Exception as e:
        print(f"Retrieval Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_audit())
