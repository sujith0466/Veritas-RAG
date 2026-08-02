import asyncio
import uuid
import structlog
from sqlalchemy import select, update, text, delete
from backend.database.engine import get_session_factory
from backend.document.models.document import Document
from backend.modules.chunking.models.chunk import DocumentChunk
from backend.modules.embedding.models.chunk_embedding import ChunkEmbedding
from backend.modules.embedding.providers.local_provider import LocalEmbeddingProvider

logger = structlog.get_logger(__name__)

async def re_embed_sync() -> None:
    session_factory = get_session_factory()
    provider = LocalEmbeddingProvider()
    
    async with session_factory() as session:
        # Find stuck documents
        stmt = select(Document.id, Document.latest_version_id, Document.tenant_id).where(Document.status.in_(["VECTOR_SYNC", "AVAILABLE", "COMPLETED"]))
        docs = (await session.execute(stmt)).all()
        
        logger.info(f"Found {len(docs)} documents to re-embed")
        for doc_id, ver_id, tenant_id in docs:
            logger.info(f"Re-embedding doc: {doc_id}")
            # Get chunks
            chunk_stmt = select(DocumentChunk).where(
                DocumentChunk.document_version_id == ver_id,
                DocumentChunk.is_deleted.is_(False)
            )
            chunks = (await session.execute(chunk_stmt)).scalars().all()
            if not chunks:
                continue
                
            contents = [c.content for c in chunks]
            embeddings = await provider.embed_documents(contents)
            
            # Delete old embeddings for this doc
            await session.execute(delete(ChunkEmbedding).where(ChunkEmbedding.document_version_id == ver_id))
            
            # Insert new embeddings
            new_embs = []
            for chunk, emb in zip(chunks, embeddings):
                new_embs.append(
                    ChunkEmbedding(
                        tenant_id=tenant_id,
                        document_version_id=ver_id,
                        chunk_id=chunk.id,
                        embedding_vector=emb,
                        dimension=len(emb),
                        model_name=provider.model_name,
                        provider="sentence_transformers",
                        content_hash=chunk.content_hash
                    )
                )
            session.add_all(new_embs)
            
            # Mark chunks as embedded
            await session.execute(update(DocumentChunk).where(DocumentChunk.document_version_id == ver_id).values(is_embedded=True))
            await session.commit()
            
if __name__ == "__main__":
    asyncio.run(re_embed_sync())
