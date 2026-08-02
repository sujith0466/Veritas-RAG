import asyncio

from sqlalchemy import select
import structlog

from backend.database.engine import get_session_factory
from backend.document.models.document import Document
from backend.modules.vector.services.vector_service import VectorStorageService

logger = structlog.get_logger(__name__)

async def repair_sync() -> None:
    session_factory = get_session_factory()

    async with session_factory() as session:
        # 1. Find all documents that have embeddings in the database
        stmt = select(Document.id, Document.latest_version_id, Document.tenant_id).where(Document.status.in_(["VECTOR_SYNC", "AVAILABLE", "COMPLETED"]))
        doc_rows = (await session.execute(stmt)).all()

        logger.info(f"Found {len(doc_rows)} documents stuck in VECTOR_SYNC")

        service = VectorStorageService(session=session)

        total_upserted = 0
        for doc_id, latest_version_id, tenant_id in doc_rows:
            logger.info(f"Syncing document {doc_id} (tenant: {tenant_id})")
            try:
                upserted_count = await service.sync_document_vectors(
                    document_id=str(doc_id),
                    document_version_id=str(latest_version_id),
                    tenant_id=tenant_id
                )
                total_upserted += upserted_count

                # Mark as AVAILABLE using an update statement instead of ORM objects
                from sqlalchemy import update
                await session.execute(
                    update(Document)
                    .where(Document.id == doc_id)
                    .values(status="AVAILABLE")
                )
                await session.commit()

            except Exception as e:
                logger.error(f"Failed to sync document {doc_id}", error=str(e))
                await session.rollback()

        logger.info(f"Repair complete. Total vectors upserted to Qdrant: {total_upserted}")

if __name__ == "__main__":
    asyncio.run(repair_sync())
