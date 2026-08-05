from datetime import datetime
from uuid import UUID

from qdrant_client.http.models import Distance, VectorParams
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.knowledge_base.models.reindex_job import VectorReindexJob
from backend.modules.knowledge_base.schemas.reindex_dto import (
    ReindexJobDTO,
    ReindexRequestDTO,
)
from backend.vector_db.client import get_qdrant_client


class VectorReindexService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.qdrant = get_qdrant_client()

    def _get_active_alias(self, workspace_id: UUID) -> str:
        return f"workspace_{workspace_id}_vectors"

    async def initiate_reindex(
        self, workspace_id: UUID, request: ReindexRequestDTO
    ) -> ReindexJobDTO:

        # Check for existing active jobs
        stmt = select(VectorReindexJob).where(
            VectorReindexJob.workspace_id == workspace_id,
            VectorReindexJob.status.in_(["INITIATED", "PROCESSING", "VERIFYING", "SWAPPING"])
        )
        res = await self.session.execute(stmt)
        existing_job = res.scalars().first()

        if existing_job and not request.force:
            raise ValueError("An active re-indexing job is already in progress.")

        if existing_job and request.force:
            existing_job.status = "CANCELLED"
            existing_job.completed_at = datetime.utcnow()
            await self.session.commit()

        # Generate unique job id first so we can use it in staging collection name
        import uuid
        job_id = uuid.uuid4()

        source_alias = self._get_active_alias(workspace_id)
        staging_collection = f"{source_alias}_staging_{job_id}"

        # Create Qdrant Collection
        # For simplicity in mock, assume dimension 1536 (OpenAI) or 768 (MiniLM)
        dim = 1536 if "openai" in request.target_model else 768

        try:
            await self.qdrant.create_collection(
                collection_name=staging_collection,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )
        except Exception as e:
            raise RuntimeError(f"Failed to create staging collection in Qdrant: {e}") from e

        # Try to find current backing collection for the alias to save as previous
        previous_collection = None
        try:
            aliases = await self.qdrant.get_aliases()
            for alias_info in aliases.aliases:
                if alias_info.alias_name == source_alias:
                    previous_collection = alias_info.collection_name
                    break
        except Exception:
            pass

        job = VectorReindexJob(
            id=job_id,
            workspace_id=workspace_id,
            status="STAGING_CREATED",
            source_alias=source_alias,
            staging_collection=staging_collection,
            previous_collection=previous_collection,
            target_model=request.target_model,
        )

        self.session.add(job)
        await self.session.commit()

        # Dispatch Celery Task
        # celery_app.send_task("reindex_workspace_vectors", args=[str(job.id)])

        return self._map_to_dto(job)

    async def get_job(self, workspace_id: UUID, job_id: UUID) -> ReindexJobDTO | None:
        stmt = select(VectorReindexJob).where(
            VectorReindexJob.id == job_id,
            VectorReindexJob.workspace_id == workspace_id
        )
        res = await self.session.execute(stmt)
        job = res.scalars().first()
        if not job:
            return None
        return self._map_to_dto(job)

    async def cancel_job(self, workspace_id: UUID, job_id: UUID) -> ReindexJobDTO:
        stmt = select(VectorReindexJob).where(
            VectorReindexJob.id == job_id,
            VectorReindexJob.workspace_id == workspace_id
        )
        res = await self.session.execute(stmt)
        job = res.scalars().first()

        if not job:
            raise ValueError("Job not found.")

        if job.status in ["COMPLETED", "ROLLED_BACK", "FAILED", "CANCELLED"]:
            raise ValueError(f"Cannot cancel job in state {job.status}")

        job.status = "CANCELLED"
        job.completed_at = datetime.utcnow()
        await self.session.commit()

        # Clean up staging collection
        try:
            await self.qdrant.delete_collection(collection_name=job.staging_collection)
        except Exception:
            pass

        return self._map_to_dto(job)

    async def rollback_job(self, workspace_id: UUID, job_id: UUID) -> ReindexJobDTO:
        stmt = select(VectorReindexJob).where(
            VectorReindexJob.id == job_id,
            VectorReindexJob.workspace_id == workspace_id
        )
        res = await self.session.execute(stmt)
        job = res.scalars().first()

        if not job:
            raise ValueError("Job not found.")

        if job.status != "COMPLETED":
            raise ValueError("Can only rollback a COMPLETED job.")

        if not job.previous_collection:
            raise ValueError("No previous collection exists for rollback.")

        from qdrant_client.http.models import (
            CreateAliasOperation,
            DeleteAliasOperation,
        )

        # Re-point alias back to previous collection
        try:
            await self.qdrant.update_collection_aliases(
                change_aliases_operations=[
                    DeleteAliasOperation(
                        delete_alias={
                            "alias_name": job.source_alias,
                            "collection_name": job.staging_collection
                        }
                    ),
                    CreateAliasOperation(
                        create_alias={
                            "alias_name": job.source_alias,
                            "collection_name": job.previous_collection
                        }
                    )
                ]
            )
        except Exception as e:
            raise RuntimeError(f"Rollback alias swap failed: {e}") from e

        job.status = "ROLLED_BACK"
        job.completed_at = datetime.utcnow()
        await self.session.commit()

        return self._map_to_dto(job)

    def _map_to_dto(self, job: VectorReindexJob) -> ReindexJobDTO:
        progress = 0.0
        if job.total_documents > 0:
            progress = (job.processed_documents / job.total_documents) * 100.0

        elapsed = None
        if job.started_at:
            end_time = job.completed_at or datetime.utcnow()
            elapsed = int((end_time - job.started_at).total_seconds())

        return ReindexJobDTO(
            id=job.id,
            workspace_id=job.workspace_id,
            status=job.status,
            progress_percentage=round(progress, 2),
            total_documents=job.total_documents,
            processed_documents=job.processed_documents,
            total_vectors_indexed=job.total_vectors_indexed,
            elapsed_time_seconds=elapsed,
            staging_collection=job.staging_collection,
            previous_collection=job.previous_collection,
            target_model=job.target_model,
            error_message=job.error_message,
            started_at=job.started_at,
            completed_at=job.completed_at,
        )
