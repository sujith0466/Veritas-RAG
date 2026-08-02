import asyncio
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
        
        doc_ver_ids = [str(d[1]) for d in docs]
        tenant_map = {str(d[1]): d[2] for d in docs}
        
        # Get all chunks
        chunk_stmt = select(DocumentChunk).where(
            DocumentChunk.document_version_id.in_(doc_ver_ids),
            DocumentChunk.is_deleted.is_(False)
        )
        chunks = (await session.execute(chunk_stmt)).scalars().all()
        logger.info(f"Found {len(chunks)} chunks to re-embed")
        
        # Embed in batches
        batch_size = 64
        new_embs = []
        
        for i in range(0, len(chunks), batch_size):
            batch_chunks = chunks[i:i+batch_size]
            contents = [c.content for c in batch_chunks]
            logger.info(f"Embedding batch {i} to {i+len(batch_chunks)}")
            result = await provider.embed_documents(contents)
            embeddings = result.embeddings
            
            for chunk, emb in zip(batch_chunks, embeddings):
                ver_id_str = str(chunk.document_version_id)
                new_embs.append(
                    ChunkEmbedding(
                        tenant_id=tenant_map[ver_id_str],
                        document_version_id=ver_id_str,
                        chunk_id=chunk.id,
                        embedding_vector=emb,
                        dimension=len(emb),
                        model_name=provider.model_name,
                        provider="sentence_transformers",
                        content_hash=chunk.content_hash
                    )
                )
        
        # Delete old embeddings for all these doc_ver_ids
        # Chunk deletion in batches of 100 to avoid long query string
        for i in range(0, len(doc_ver_ids), 100):
            batch_ver_ids = doc_ver_ids[i:i+100]
            await session.execute(delete(ChunkEmbedding).where(ChunkEmbedding.document_version_id.in_(batch_ver_ids)))
            
        session.add_all(new_embs)
        
        # Update chunks
        for i in range(0, len(doc_ver_ids), 100):
            batch_ver_ids = doc_ver_ids[i:i+100]
            await session.execute(update(DocumentChunk).where(DocumentChunk.document_version_id.in_(batch_ver_ids)).values(is_embedded=True))
            
        await session.commit()
        logger.info("Done inserting into DB!")
            
if __name__ == "__main__":
    asyncio.run(re_embed_sync())
