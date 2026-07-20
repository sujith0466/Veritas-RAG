"""Vector storage Celery worker tasks package (`ADR-M3-001`)."""

from backend.modules.vector.workers.tasks import sync_vectors_to_qdrant_task

__all__ = ["sync_vectors_to_qdrant_task"]
