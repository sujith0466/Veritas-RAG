"""Celery tasks for data retention lifecycle sweeps (F13.3 Document Retention, F13.4 Chat Retention)."""

import asyncio
import datetime
import logging
import uuid

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.cache.client import get_redis_client
from backend.database.engine import get_session_factory
from backend.document.models.document import Document
from backend.document.storage import LocalStorageProvider
from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.models.entities.workspace_settings import WorkspaceSettings
from backend.modules.chat.models.chat_session import ChatSession
from backend.modules.vector.services.vector_service import VectorStorageService
from backend.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


async def _push_to_dlq(task_name: str, payload: dict, error_msg: str) -> None:
    """Record unrecoverable retention job failure into Redis DLQ."""
    redis = get_redis_client()
    if redis:
        try:
            dlq_item = {
                "task": task_name,
                "payload": payload,
                "error": error_msg,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }
            import json
            await redis.rpush("retention:dlq", json.dumps(dlq_item))
        except Exception as e:
            logger.warning("Failed pushing to retention DLQ: %s", e)


async def _run_document_retention_sweep() -> dict:
    """Orchestrate multi-tenant document retention sweep."""
    summary = {
        "workspaces_evaluated": 0,
        "documents_soft_deleted": 0,
        "documents_hard_deleted": 0,
        "qdrant_cleaned": 0,
        "storage_cleaned": 0,
        "errors": 0,
    }

    session_factory = get_session_factory()
    storage = LocalStorageProvider()

    async with session_factory() as session:
        # 1. Fetch active workspaces
        stmt = select(Workspace).where(
            Workspace.status == WorkspaceStatus.ACTIVE.value,
            Workspace.is_deleted == False,
        )
        res = await session.execute(stmt)
        workspaces = list(res.scalars().all())

    for ws in workspaces:
        summary["workspaces_evaluated"] += 1
        ws_id = ws.id
        tenant_id = ws.slug or str(ws.id)

        try:
            async with session_factory() as session:
                # Read retention settings
                s_stmt = select(WorkspaceSettings).where(WorkspaceSettings.workspace_id == ws_id)
                s_res = await session.execute(s_stmt)
                ws_settings = s_res.scalar_one_or_none()

                retention_days = 365
                if ws_settings and ws_settings.settings_json:
                    retention_days = ws_settings.settings_json.get("general", {}).get("retention_days", 365)

                if retention_days <= 0:
                    continue

                cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=retention_days)

                # Query eligible documents using SKIP LOCKED
                doc_stmt = (
                    select(Document.id, Document.tenant_id)
                    .where(
                        (Document.tenant_id == tenant_id) | (Document.tenant_id == str(ws_id)),
                        Document.is_deleted == False,
                        Document.created_at < cutoff,
                        Document.status.not_in(["PROCESSING", "PENDING"]),
                    )
                    .with_for_update(skip_locked=True)
                )
                doc_res = await session.execute(doc_stmt)
                eligible_docs = list(doc_res.all())

                if not eligible_docs:
                    continue

                doc_ids = [d[0] for d in eligible_docs]
                doc_tenants = {d[0]: d[1] for d in eligible_docs}

                # Phase 1: Soft-delete in PostgreSQL
                await session.execute(
                    update(Document)
                    .where(Document.id.in_(doc_ids))
                    .values(is_deleted=True)
                )
                await session.commit()
                summary["documents_soft_deleted"] += len(doc_ids)

                # Phase 2: Delete vectors in Qdrant (best-effort)
                vector_service = VectorStorageService(session=session)
                for doc_id in doc_ids:
                    t_id = doc_tenants.get(doc_id, tenant_id)
                    try:
                        await vector_service.remove_archived_document_vectors(
                            document_id=str(doc_id),
                            tenant_id=t_id,
                        )
                        summary["qdrant_cleaned"] += 1
                    except Exception as q_err:
                        logger.warning("Retention: Qdrant cleanup failed for doc %s: %s", doc_id, q_err)

                # Phase 3: Delete physical files from object storage (best-effort)
                for doc_id in doc_ids:
                    t_id = doc_tenants.get(doc_id, tenant_id)
                    try:
                        prefix = f"documents/{t_id}/{doc_id}"
                        await storage.delete_prefix(prefix)
                        summary["storage_cleaned"] += 1
                    except Exception as s_err:
                        logger.warning("Retention: Storage cleanup failed for doc %s: %s", doc_id, s_err)

                # Phase 4: Hard delete document rows in PostgreSQL
                await session.execute(
                    delete(Document).where(Document.id.in_(doc_ids))
                )
                await session.commit()
                summary["documents_hard_deleted"] += len(doc_ids)

        except Exception as e:
            summary["errors"] += 1
            logger.error("Document retention sweep failed for workspace %s: %s", ws_id, e)

    return summary


async def _run_chat_retention_sweep() -> dict:
    """Orchestrate chat history retention sweep across all active workspaces."""
    summary = {
        "workspaces_evaluated": 0,
        "sessions_deleted": 0,
        "errors": 0,
    }

    session_factory = get_session_factory()

    async with session_factory() as session:
        stmt = select(Workspace).where(
            Workspace.status == WorkspaceStatus.ACTIVE.value,
            Workspace.is_deleted == False,
        )
        res = await session.execute(stmt)
        workspaces = list(res.scalars().all())

    for ws in workspaces:
        summary["workspaces_evaluated"] += 1
        ws_id = ws.id
        tenant_id = ws.slug or str(ws.id)

        try:
            async with session_factory() as session:
                s_stmt = select(WorkspaceSettings).where(WorkspaceSettings.workspace_id == ws_id)
                s_res = await session.execute(s_stmt)
                ws_settings = s_res.scalar_one_or_none()

                retention_days = 365
                if ws_settings and ws_settings.settings_json:
                    retention_days = ws_settings.settings_json.get("general", {}).get("retention_days", 365)

                if retention_days <= 0:
                    continue

                cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=retention_days)

                # Pinned sessions are EXEMPT from automatic purge
                chat_stmt = (
                    select(ChatSession.id)
                    .where(
                        (ChatSession.tenant_id == tenant_id) | (ChatSession.tenant_id == str(ws_id)),
                        ChatSession.created_at < cutoff,
                        ChatSession.pinned == False,
                    )
                    .with_for_update(skip_locked=True)
                )
                chat_res = await session.execute(chat_stmt)
                session_ids = [row[0] for row in chat_res.all()]

                if not session_ids:
                    continue

                # Hard delete sessions (cascades to chat_messages)
                await session.execute(
                    delete(ChatSession).where(ChatSession.id.in_(session_ids))
                )
                await session.commit()
                summary["sessions_deleted"] += len(session_ids)

        except Exception as e:
            summary["errors"] += 1
            logger.error("Chat retention sweep failed for workspace %s: %s", ws_id, e)

    return summary


@celery_app.task(
    name="backend.tasks.retention.run_document_retention_sweep_task",
    bind=True,
    queue="retention",
    max_retries=3,
    default_retry_delay=300,
    acks_late=True,
    reject_on_worker_lost=True,
)
def run_document_retention_sweep_task(self) -> dict:
    """Celery task entry point for document retention sweep."""
    try:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(_run_document_retention_sweep())
    except Exception as exc:
        logger.error("Document retention sweep task failed: %s", exc)
        if self.request.retries >= self.max_retries:
            try:
                loop.run_until_complete(_push_to_dlq("document_retention_sweep", {}, str(exc)))
            except Exception:
                pass
        raise self.retry(exc=exc, countdown=300)


@celery_app.task(
    name="backend.tasks.retention.run_chat_retention_sweep_task",
    bind=True,
    queue="retention",
    max_retries=3,
    default_retry_delay=300,
    acks_late=True,
    reject_on_worker_lost=True,
)
def run_chat_retention_sweep_task(self) -> dict:
    """Celery task entry point for chat session retention sweep."""
    try:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(_run_chat_retention_sweep())
    except Exception as exc:
        logger.error("Chat retention sweep task failed: %s", exc)
        if self.request.retries >= self.max_retries:
            try:
                loop.run_until_complete(_push_to_dlq("chat_retention_sweep", {}, str(exc)))
            except Exception:
                pass
        raise self.retry(exc=exc, countdown=300)
