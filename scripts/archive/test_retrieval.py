import asyncio
from backend.modules.retrieval.api.dependencies import get_retrieval_orchestrator, get_retrieval_repository, get_sparse_index_manager, _qdrant_provider, _bm25_provider, _reranker_provider
from backend.database.engine import get_session_factory
from backend.modules.retrieval.schemas.retrieval_dto import SearchRequestDTO
from backend.modules.retrieval.repositories.retrieval_repository import RetrievalRepository

async def test_retrieval():
    session_factory = get_session_factory()
    async with session_factory() as session:
        repo = RetrievalRepository(session=session)
        index_manager = get_sparse_index_manager()
        
        # We need to manually construct the orchestrator like dependencies.py does
        from backend.modules.embedding.providers.local_provider import LocalEmbeddingProvider
        from backend.core.config import get_settings
        from backend.core.events.dispatcher import get_dispatcher
        
        settings = get_settings()
        embedding_provider = LocalEmbeddingProvider(model_name=settings.embeddings.local_model, offline=False)
        
        orchestrator = get_retrieval_orchestrator(repo, index_manager)
        
        # We also need to supply the real providers to the orchestrator since dependencies injects them
        orchestrator.embedding_provider = embedding_provider
        
        query = SearchRequestDTO(
            query="How do I configure the fallback models in RAGuard?",
            tenant_id="raguard_corp",
            top_k=5,
            semantic_weight=0.7,
            strategy="hybrid"
        )
        
        print(f"Executing Query: {query.query}")
        results = await orchestrator.execute_hybrid_search(options=query, tenant_id="raguard_corp")
        
        print("\n--- RETRIEVAL RESULTS ---")
        print(f"Total Evidences Returned: {len(results.final_evidence)}")
        for i, ev in enumerate(results.final_evidence):
            print(f"\n[Evidence {i+1}]")
            print(f"Content: {ev.content[:200]}...")
            print("-" * 50)

if __name__ == "__main__":
    asyncio.run(test_retrieval())
