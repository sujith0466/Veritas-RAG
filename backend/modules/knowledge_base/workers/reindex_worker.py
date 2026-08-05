import asyncio
from uuid import UUID

from celery import shared_task
from qdrant_client.http.models import PointStruct
from sqlalchemy import select

from backend.core.database import get_db_session
from backend.document.models import Document, DocumentVersion
from backend.modules.chunking.models import DocumentChunk
from backend.modules.knowledge_base.models.reindex_job import VectorReindexJob
from backend.vector_db.client import get_qdrant_client


async def _process_reindex_job_async(job_id: UUID) -> None:
    async with get_db_session() as session:
        stmt = select(VectorReindexJob).where(VectorReindexJob.id == job_id)
        res = await session.execute(stmt)
        job = res.scalars().first()

        if not job:
            return

        try:
            job.status = "INDEXING"
            await session.commit()

            # Find all active documents in the workspace
            doc_stmt = select(Document, DocumentVersion).join(
                DocumentVersion, Document.active_version_id == DocumentVersion.id
            ).where(
                Document.tenant_id == job.workspace_id,
                not Document.is_deleted
            )
            doc_res = await session.execute(doc_stmt)
            active_docs = doc_res.all()

            job.total_documents = len(active_docs)
            await session.commit()

            qdrant = get_qdrant_client()

            for doc, ver in active_docs:
                # Fetch all chunks for this version
                chunk_stmt = select(DocumentChunk).where(
                    DocumentChunk.document_version_id == ver.id
                )
                chunk_res = await session.execute(chunk_stmt)
                chunks = chunk_res.scalars().all()

                # In a real scenario, we would re-run embedding generation here using the target_model
                # For this mock implementation, we just create dummy vectors or use existing payload
                # We'll insert points into the staging collection

                points: list[PointStruct] = []
                dim = 1536 if "openai" in job.target_model else 768

                for _idx, chunk in enumerate(chunks):
                    # Mocking new vector based on target_model dimension
                    mock_vector = [0.0] * dim
                    points.append(
                        PointStruct(
                            id=str(chunk.id),
                            vector=mock_vector,
                            payload={
                                "workspace_id": str(job.workspace_id),
                                "document_id": str(doc.id),
                                "chunk_id": str(chunk.id),
                                "text": chunk.text,
                            }
                        )
                    )

                if points:
                    await qdrant.upsert(
                        collection_name=job.staging_collection,
                        points=points
                    )
                    job.total_vectors_indexed += len(points)

                job.processed_documents += 1

                # Optional: Update progress periodically, we just update per document here
                await session.commit()

            # Verification phase
            job.status = "VERIFYING"
            await session.commit()

            # Simple parity check: count points in staging
            q_count = await qdrant.count(collection_name=job.staging_collection, exact=True)
            if q_count.count == job.total_vectors_indexed:
                job.parity_verified = True
            else:
                raise ValueError("Parity verification failed between indexed vectors and staging collection count.")

            # Swap Alias phase
            job.status = "SWAPPING"
            await session.commit()

            from qdrant_client.http.models import (
                CreateAliasOperation,
                DeleteAliasOperation,
            )

            ops = []
            if job.previous_collection:
                # Need to check if there is an active collection behind the alias
                ops.append(
                    DeleteAliasOperation(
                        delete_alias={
                            "alias_name": job.source_alias,
                            "collection_name": job.previous_collection
                        }
                    )
                )

            ops.append(
                CreateAliasOperation(
                    create_alias={
                        "alias_name": job.source_alias,
                        "collection_name": job.staging_collection
                    }
                )
            )

            await qdrant.update_collection_aliases(change_aliases_operations=ops)

            job.status = "COMPLETED"

        except Exception as e:
            job.status = "FAILED"
            job.error_message = str(e)

        finally:
            from datetime import datetime
            job.completed_at = datetime.utcnow()
            await session.commit()


@shared_task(name="reindex_workspace_vectors")
def reindex_workspace_vectors(job_id: str) -> None:
    """Celery background task to execute the blue-green re-indexing workflow."""
    asyncio.run(_process_reindex_job_async(UUID(job_id)))
