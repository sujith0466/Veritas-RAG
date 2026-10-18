"""Veritas-RAG P0-3 End-to-End Lifecycle Verification Suite.

Tests live multi-version document lifecycle, zero-downtime version promotion,
candidate validation, and multi-tenant isolation across running PostgreSQL,
Redis, Qdrant, and Celery worker services.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import io
from pathlib import Path
import time
from typing import Any
import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.core.events.base import BaseEvent
from backend.core.events.types import EventType
from backend.document.models.document import Document, DocumentVersion
from backend.document.models.job import ProcessingJob
from backend.document.models.status import DocumentStatus
from backend.document.services.document_service import DocumentService
from backend.models.entities.user import User
from backend.document.storage.local import LocalStorageProvider
from backend.modules.chunking.models.chunk import DocumentChunk
from backend.modules.embedding.models.embedding_job import EmbeddingJob
from backend.modules.embedding.providers.local_provider import LocalEmbeddingProvider
from backend.modules.retrieval.providers.reranker.local_reranker import LocalCrossEncoderProvider
from backend.modules.retrieval.providers.sparse.bm25_provider import BM25SparseSearchProvider
from backend.modules.retrieval.repositories.retrieval_repository import RetrievalRepository
from backend.modules.retrieval.schemas.retrieval_dto import SearchRequestDTO
from backend.modules.retrieval.services.bm25_manager import SparseIndexManager
from backend.modules.retrieval.services.retrieval_service import RetrievalOrchestrator
from backend.modules.vector.models.vector_metadata import VectorIndexMetadata
from backend.modules.vector.providers.qdrant_provider import QdrantVectorDBProvider
from backend.tasks.listeners import handle_vector_sync_completed
from tests.e2e.conftest import (
    E2E_CELERY_BROKER,
    cleanup_run_qdrant_collections,
    cleanup_tenant_database_records,
    cleanup_tenant_storage_artifacts,
    drain_celery_queues_and_verify_quiescence,
    pause_indexing_consumer,
    resume_indexing_consumer,
)


# ── Canonical Event Definition ────────────────────────────────────────────────

@dataclass(frozen=True)
class RealVectorIndexedEvent(BaseEvent):
    """Matches the exact schema emitted by backend/modules/vector/workers/tasks.py."""
    document_id: str = ""
    document_version_id: str = ""
    tenant_id: str = ""
    data: dict = field(default_factory=dict)
    event_type: EventType = EventType.VECTORS_INDEXED


# ── Helper Utilities ─────────────────────────────────────────────────────────

async def poll_with_fresh_session(
    session_factory: async_sessionmaker[AsyncSession],
    check_fn: Any,
    timeout: float = 45.0,
    interval: float = 0.5,
    description: str = "condition",
) -> Any:
    """Poll condition using a fresh session per query to eliminate stale ORM identity-map caching."""
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        async with session_factory() as session:
            result = await check_fn(session)
            if result:
                return result
        await asyncio.sleep(interval)
    raise TimeoutError(f"Timed out after {timeout}s waiting for: {description}")


# ── Master Lifecycle Test ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_p0_3_full_lifecycle_and_zero_downtime_promotion(
    e2e_preflight_verified: None,  # Mandatory preflight dependency: fails closed on runner/worker mismatch
    e2e_run_id: str,
    e2e_storage_root: Path,
    e2e_tenant_a: str,
    e2e_tenant_b: str,
    e2e_session: AsyncSession,
    e2e_session_factory: async_sessionmaker[AsyncSession],
    e2e_celery_app: Any,
    e2e_qdrant_client: Any,
) -> None:
    """Master Verification: Scenarios 1 through 6.

    1. Zero-downtime V1 retrievability while V2 is in-flight.
    2. Synchronous V2 promotion upon vector synchronization.
    3A. Parser/Ingestion failure leaves active version retrievable.
    4. Stale vector-sync event monotonic gate rejection.
    5. Dense and BM25 active-version agreement using real chunk records.
    6. Multi-tenant boundary isolation using real Tenant A chunks.
    """
    # Initialize LocalStorageProvider with the shared host scratch directory
    storage_provider = LocalStorageProvider(root_path=e2e_storage_root)
    doc_service = DocumentService(storage_provider=storage_provider)
    owner_id = uuid.uuid4()
    doc_id: uuid.UUID | None = None
    v1_id: uuid.UUID | None = None
    v2_id: uuid.UUID | None = None

    try:
        # Ensure owner user exists in database to satisfy foreign key constraints
        owner_user = User(
            id=owner_id,
            email=f"e2e_owner_{e2e_run_id}@example.com",
            role="owner",
            is_active=True,
        )
        e2e_session.add(owner_user)
        await e2e_session.commit()

        # ──────────────────────────────────────────────────────────────────────
        # STEP 1: Upload and Index Initial Version (V1)
        # ──────────────────────────────────────────────────────────────────────
        v1_content = (
            "Veritas-RAG Architecture V1: Initial production baseline for document ingestion. "
            "Microservice architecture with decoupled worker pools and vector search."
        )
        stream_v1 = io.BytesIO(v1_content.encode("utf-8"))

        doc, v1, job1 = await doc_service.upload_document(
            stream=stream_v1,
            filename="architecture.txt",
            declared_mime="text/plain",
            tenant_id=e2e_tenant_a,
            owner_user_id=owner_id,
            session=e2e_session,
        )
        doc_id = doc.id
        v1_id = v1.id

        # Wait until V1 pipeline finishes: Document becomes READY with latest_version_id == v1_id
        async def check_v1_ready(session: AsyncSession) -> bool:
            stmt = select(Document).where(Document.id == doc_id)
            d = (await session.execute(stmt)).scalar_one_or_none()
            return d is not None and d.status == DocumentStatus.READY and d.latest_version_id == v1_id

        await poll_with_fresh_session(
            e2e_session_factory, check_v1_ready, timeout=45.0, description="V1 pipeline completion"
        )

        # Verify V1 is active in PostgreSQL
        async with e2e_session_factory() as session:
            v1_record = await session.get(DocumentVersion, v1_id)
            assert v1_record is not None
            assert v1_record.is_active_vector is True, "V1 must be active vector upon initial index"

        # ──────────────────────────────────────────────────────────────────────
        # STEP 2 (Scenario 1): Pause Indexing & Upload V2 (In-Flight Zero Downtime)
        # ──────────────────────────────────────────────────────────────────────
        # Pause indexing queue so V2 vector sync cannot run yet
        await pause_indexing_consumer(e2e_celery_app)

        v2_content = (
            "Veritas-RAG Architecture V2: Enhanced cloud-native pipeline with zero-downtime "
            "version promotion and monotonic gate guards."
        )
        stream_v2 = io.BytesIO(v2_content.encode("utf-8"))

        doc, v2, job2 = await doc_service.upload_new_version(
            document_id=doc_id,
            stream=stream_v2,
            filename="architecture.txt",
            declared_mime="text/plain",
            tenant_id=e2e_tenant_a,
            owner_user_id=owner_id,
            session=e2e_session,
        )
        v2_id = v2.id

        # Wait until V2 completes embedding (ingestion + chunking + embeddings finished)
        async def check_v2_embedded(session: AsyncSession) -> bool:
            res = await session.execute(
                select(EmbeddingJob).where(
                    EmbeddingJob.document_version_id == v2_id,
                    EmbeddingJob.status == "COMPLETED",
                )
            )
            return res.scalar_one_or_none() is not None

        await poll_with_fresh_session(
            e2e_session_factory, check_v2_embedded, timeout=45.0, description="V2 embedding completion"
        )

        # Assert: V2 vector sync has NOT executed yet (indexing queue is paused)
        async with e2e_session_factory() as session:
            doc_polled = await session.get(Document, doc_id)
            v2_record = await session.get(DocumentVersion, v2_id)
            assert doc_polled is not None
            assert v2_record is not None
            assert v2_record.is_active_vector is False, "V2 must not be active while vector sync is pending"

            # Assert zero-downtime contract: Document remains READY and serves V1
            assert doc_polled.status == DocumentStatus.READY, "Document must remain READY during V2 in-flight processing"
            assert doc_polled.latest_version_id == v1_id, "latest_version_id must stay on V1 during V2 processing"

        # ──────────────────────────────────────────────────────────────────────
        # STEP 3 (Scenario 2): Resume Indexing & Observe Monotonic V2 Promotion
        # ──────────────────────────────────────────────────────────────────────
        await resume_indexing_consumer(e2e_celery_app)

        # Wait until V2 vector sync completes and promotes document
        async def check_v2_promoted(session: AsyncSession) -> bool:
            d = await session.get(Document, doc_id)
            v2_ref = await session.get(DocumentVersion, v2_id)
            return (
                d is not None
                and d.latest_version_id == v2_id
                and v2_ref is not None
                and v2_ref.is_active_vector is True
            )

        await poll_with_fresh_session(
            e2e_session_factory, check_v2_promoted, timeout=45.0, description="V2 vector sync and promotion"
        )

        # Assert: V1 deactivated and V2 promoted
        async with e2e_session_factory() as session:
            v1_ref = await session.get(DocumentVersion, v1_id)
            doc_ref = await session.get(Document, doc_id)
            assert v1_ref is not None and v1_ref.is_active_vector is False, "V1 must be deactivated upon V2 promotion"
            assert doc_ref is not None and doc_ref.latest_version_id == v2_id, "latest_version_id must point to V2"
            assert doc_ref.status == DocumentStatus.READY

        # ──────────────────────────────────────────────────────────────────────
        # STEP 4 (Scenario 4): Stale V1 Event Rejection (Monotonic Version Guard)
        # ──────────────────────────────────────────────────────────────────────
        # NOTE: Validates in-process handler logic of handle_vector_sync_completed;
        # distributed Celery broker delivery for out-of-order events is unverified in this test.
        stale_v1_event = RealVectorIndexedEvent(
            document_id=str(doc_id),
            document_version_id=str(v1_id),
            tenant_id=e2e_tenant_a,
            data={
                "upserted_points": 1,
                "document_version_id": str(v1_id),
                "version_id": str(v1_id),
                "document_id": str(doc_id),
            },
        )

        # Deliver stale event through actual lifecycle handler
        await handle_vector_sync_completed(stale_v1_event)

        # Assert: Monotonic gate ignored the older version
        async with e2e_session_factory() as session:
            doc_after_stale = await session.get(Document, doc_id)
            v1_after_stale = await session.get(DocumentVersion, v1_id)
            assert doc_after_stale is not None and doc_after_stale.latest_version_id == v2_id, (
                "Monotonic gate must NOT regress active version to V1"
            )
            assert v1_after_stale is not None and v1_after_stale.is_active_vector is False, (
                "V1 must remain inactive"
            )

        # ──────────────────────────────────────────────────────────────────────
        # STEP 5 (Scenario 3A): Parser/Ingestion Failure Leaves Active Version Ready
        # ──────────────────────────────────────────────────────────────────────
        # Corrupted payload that triggers extraction failure in worker
        corrupted_stream = io.BytesIO(b"%PDF-1.4\nINVALID_CORRUPTED_PARSER_PAYLOAD")

        doc, v3, job3 = await doc_service.upload_new_version(
            document_id=doc_id,
            stream=corrupted_stream,
            filename="corrupted_report.pdf",
            declared_mime="application/pdf",
            tenant_id=e2e_tenant_a,
            owner_user_id=owner_id,
            session=e2e_session,
        )

        # Wait for processing job to fail
        async def check_v3_failed(session: AsyncSession) -> bool:
            j = await session.get(ProcessingJob, job3.id)
            return j is not None and j.status in ("FAILED", "error")

        await poll_with_fresh_session(
            e2e_session_factory, check_v3_failed, timeout=30.0, description="V3 job failure"
        )

        # Ingestion failure preserves READY status because V2 is active
        async with e2e_session_factory() as session:
            doc_after_fail = await session.get(Document, doc_id)
            assert doc_after_fail is not None and doc_after_fail.status == DocumentStatus.READY, (
                "Document status must remain READY when an in-flight version fails extraction"
            )
            assert doc_after_fail.latest_version_id == v2_id, "latest_version_id must remain on V2"

        # ──────────────────────────────────────────────────────────────────────
        # STEP 5B: Upload Tenant B Document with Overlapping Terminology
        # ──────────────────────────────────────────────────────────────────────
        # Guarantees both tenants hold real active content for genuine isolation testing
        b_content = (
            "Veritas-RAG Architecture Tenant B: Partitioned workspace and isolated knowledge base "
            "for multi-tenant retrieval boundary verification."
        )
        stream_b = io.BytesIO(b_content.encode("utf-8"))
        doc_b, v1_b, job_b = await doc_service.upload_document(
            stream=stream_b,
            filename="tenant_b_architecture.txt",
            declared_mime="text/plain",
            tenant_id=e2e_tenant_b,
            owner_user_id=owner_id,
            session=e2e_session,
        )

        async def check_tb_ready(session: AsyncSession) -> bool:
            stmt = select(Document).where(Document.id == doc_b.id)
            d = (await session.execute(stmt)).scalar_one_or_none()
            return d is not None and d.status == DocumentStatus.READY and d.latest_version_id == v1_b.id

        await poll_with_fresh_session(
            e2e_session_factory, check_tb_ready, timeout=45.0, description="Tenant B pipeline completion"
        )

        # ──────────────────────────────────────────────────────────────────────
        # STEP 6 (Scenario 5 & 6): Real Dense Search, BM25, and Multi-Tenant Isolation
        # ──────────────────────────────────────────────────────────────────────
        # 1. Real Database Chunks Verification for Both Tenants
        res_v1_chunks = await e2e_session.execute(
            select(DocumentChunk).where(
                DocumentChunk.document_id == doc_id,
                DocumentChunk.document_version_id == v1_id,
            )
        )
        real_v1_chunks = res_v1_chunks.scalars().all()
        assert len(real_v1_chunks) > 0, "Real V1 chunks must exist in test database"

        res_v2_chunks = await e2e_session.execute(
            select(DocumentChunk).where(
                DocumentChunk.document_id == doc_id,
                DocumentChunk.document_version_id == v2_id,
            )
        )
        real_v2_chunks = res_v2_chunks.scalars().all()
        assert len(real_v2_chunks) > 0, "Real V2 chunks must exist in test database"

        res_tb_chunks = await e2e_session.execute(
            select(DocumentChunk).where(
                DocumentChunk.document_id == doc_b.id,
                DocumentChunk.document_version_id == v1_b.id,
            )
        )
        real_tb_chunks = res_tb_chunks.scalars().all()
        assert len(real_tb_chunks) > 0, "Real Tenant B chunks must exist in test database"

        real_v1_tuples = {(c.id, c.document_id, c.document_version_id) for c in real_v1_chunks}
        real_v2_tuples = {(c.id, c.document_id, c.document_version_id) for c in real_v2_chunks}
        real_tb_tuples = {(c.id, c.document_id, c.document_version_id) for c in real_tb_chunks}
        all_real_tuples = real_v1_tuples | real_v2_tuples

        repo = RetrievalRepository(e2e_session)

        # 2. Genuine Dense Vector Search against Qdrant
        # Look up recorded collection names from VectorIndexMetadata
        meta_stmt_a = select(VectorIndexMetadata.collection_name).where(
            VectorIndexMetadata.tenant_id == e2e_tenant_a,
            VectorIndexMetadata.document_id == doc_id,
            VectorIndexMetadata.document_version_id == v2_id,
        )
        col_res_a = await e2e_session.execute(meta_stmt_a)
        col_name_a = col_res_a.scalar_one_or_none()
        assert col_name_a is not None, "Target Qdrant collection A must be recorded in vector metadata"

        meta_stmt_b = select(VectorIndexMetadata.collection_name).where(
            VectorIndexMetadata.tenant_id == e2e_tenant_b,
            VectorIndexMetadata.document_id == doc_b.id,
            VectorIndexMetadata.document_version_id == v1_b.id,
        )
        col_res_b = await e2e_session.execute(meta_stmt_b)
        col_name_b = col_res_b.scalar_one_or_none()
        assert col_name_b is not None, "Target Qdrant collection B must be recorded in vector metadata"

        embedding_provider = LocalEmbeddingProvider()
        query_vector = await embedding_provider.embed_query("Veritas-RAG Architecture")
        assert len(query_vector) > 0, "Query vector must be generated"

        vector_provider = QdrantVectorDBProvider(client=e2e_qdrant_client)
        dense_hits_a = await vector_provider.search_points(
            collection_name=col_name_a,
            query_vector=query_vector,
            filter_conditions={"tenant_id": e2e_tenant_a},
            limit=10,
        )
        assert len(dense_hits_a) > 0, "Dense vector search against Qdrant must return indexed hits"

        # Extract structured candidate tuples from real Qdrant hits
        qdrant_candidate_tuples = set()
        for hit in dense_hits_a:
            p = hit.get("payload", {})
            chunk_id = p.get("chunk_id") or hit.get("point_id")
            if chunk_id and p.get("document_id") and p.get("document_version_id"):
                qdrant_candidate_tuples.add((
                    uuid.UUID(str(chunk_id)),
                    uuid.UUID(str(p["document_id"])),
                    uuid.UUID(str(p["document_version_id"])),
                ))

        assert len(qdrant_candidate_tuples) > 0, "Qdrant hits must contain structured chunk metadata tuples"

        # Validate dense candidates against PostgreSQL authoritative state (Stage 2.5)
        # Demonstrates distinction: raw Qdrant vectors vs candidates approved by authoritative DB gate
        valid_dense_a = await repo.validate_active_candidates(qdrant_candidate_tuples, e2e_tenant_a)
        assert len(valid_dense_a) > 0, "Active V2 dense candidates must pass candidate validation"
        for t in valid_dense_a:
            assert t[2] == v2_id, f"Validated candidate chunk {t[0]} must belong to promoted V2"

        # Assert superseded V1 chunks are rejected by authoritative DB gate
        for t in real_v1_tuples:
            assert t not in valid_dense_a, f"Superseded V1 chunk {t[0]} must be rejected"

        # 3. Dense Multi-Tenant Isolation
        # Cross-tenant query on Collection A with Tenant B filter returns 0 hits
        cross_hits = await vector_provider.search_points(
            collection_name=col_name_a,
            query_vector=query_vector,
            filter_conditions={"tenant_id": e2e_tenant_b},
            limit=10,
        )
        assert len(cross_hits) == 0, (
            "Cross-tenant dense search in Qdrant must return 0 hits for Tenant B on Collection A"
        )

        # Genuine Tenant B dense query against Collection B returns Tenant B points
        dense_hits_b = await vector_provider.search_points(
            collection_name=col_name_b,
            query_vector=query_vector,
            filter_conditions={"tenant_id": e2e_tenant_b},
            limit=10,
        )
        assert len(dense_hits_b) > 0, "Dense vector search for Tenant B must return Tenant B hits"
        for hit in dense_hits_b:
            assert hit.get("payload", {}).get("tenant_id") == e2e_tenant_b

        # 4. Genuine BM25 Retrieval Path & Namespace Isolation with Overlapping Terms
        bm25_provider = BM25SparseSearchProvider()
        bm25_manager = SparseIndexManager(sparse_provider=bm25_provider, redis=None)

        # Tenant A: Rebuild index and query overlapping term "architecture"
        await bm25_manager.rebuild_index(e2e_tenant_a)
        bm25_candidates_a = await bm25_provider.search_keywords(e2e_tenant_a, query="architecture", limit=10)
        assert len(bm25_candidates_a) > 0, "BM25 retrieval must return candidates for Tenant A"
        for candidate in bm25_candidates_a:
            assert candidate.tenant_id == e2e_tenant_a
            assert candidate.document_version_id == v2_id, (
                f"BM25 candidate chunk {candidate.chunk_id} must belong to active version V2"
            )

        # Tenant B: Rebuild index and query same overlapping term "architecture"
        await bm25_manager.rebuild_index(e2e_tenant_b)
        bm25_candidates_b = await bm25_provider.search_keywords(e2e_tenant_b, query="architecture", limit=10)
        assert len(bm25_candidates_b) > 0, "BM25 retrieval must return candidates for Tenant B"
        for candidate in bm25_candidates_b:
            assert candidate.tenant_id == e2e_tenant_b
            assert candidate.document_version_id == v1_b.id, (
                f"BM25 candidate chunk {candidate.chunk_id} must belong to Tenant B version V1_B"
            )

        # Strict isolation check: candidate sets across tenants must be completely disjoint
        chunk_ids_a = {c.chunk_id for c in bm25_candidates_a}
        chunk_ids_b = {c.chunk_id for c in bm25_candidates_b}
        assert chunk_ids_a.isdisjoint(chunk_ids_b), (
            "Multi-tenant BM25 isolation violated: common chunk detected across distinct tenants"
        )

        # 5. Complete Production Retrieval Pipeline (RetrievalOrchestrator)
        orchestrator = RetrievalOrchestrator(
            embedding_provider=embedding_provider,
            vector_provider=vector_provider,
            sparse_provider=bm25_provider,
            reranker_provider=LocalCrossEncoderProvider(),
            repository=repo,
            index_manager=bm25_manager,
        )

        # Tenant A: Complete Hybrid Search
        search_req_a = SearchRequestDTO(query="architecture", top_k=5)
        res_a = await orchestrator.execute_hybrid_search(search_req_a, tenant_id=e2e_tenant_a)
        assert len(res_a.final_evidence) > 0, "Hybrid search must return ranked evidence for Tenant A"
        for ev in res_a.final_evidence:
            assert ev.tenant_id == e2e_tenant_a
            assert ev.document_version_id == v2_id, (
                f"Hybrid evidence {ev.chunk_id} must belong to promoted active version V2"
            )

        # Tenant B: Complete Hybrid Search
        search_req_b = SearchRequestDTO(query="architecture", top_k=5)
        res_b = await orchestrator.execute_hybrid_search(search_req_b, tenant_id=e2e_tenant_b)
        assert len(res_b.final_evidence) > 0, "Hybrid search must return ranked evidence for Tenant B"
        for ev in res_b.final_evidence:
            assert ev.tenant_id == e2e_tenant_b
            assert ev.document_version_id == v1_b.id, (
                f"Hybrid evidence {ev.chunk_id} must belong to Tenant B version V1_B"
            )

        # Cross-Tenant Evidence Disjointness
        ev_ids_a = {ev.chunk_id for ev in res_a.final_evidence}
        ev_ids_b = {ev.chunk_id for ev in res_b.final_evidence}
        assert ev_ids_a.isdisjoint(ev_ids_b), "Hybrid search leaked cross-tenant evidence"

        # 6. Authoritative Cross-Tenant Candidate Validation Probe
        valid_b = await repo.validate_active_candidates(all_real_tuples, e2e_tenant_b)
        assert len(valid_b) == 0, (
            "Cross-tenant candidate validation must return 0 valid candidates for real Tenant A chunks"
        )

    finally:
        # ──────────────────────────────────────────────────────────────────────
        # TEARDOWN: Verifiable, non-suppressed cleanup restricted to current run
        # ──────────────────────────────────────────────────────────────────────
        # 0. Rollback any pending or failed transaction on e2e_session
        try:
            await e2e_session.rollback()
        except Exception:
            pass

        # 1. Drain all 7 Celery queues and verify complete worker quiescence
        await drain_celery_queues_and_verify_quiescence(e2e_celery_app, E2E_CELERY_BROKER)

        # 2. Purge Tenant A & B database records and independently verify
        await cleanup_tenant_database_records(e2e_session, e2e_tenant_a)
        await cleanup_tenant_database_records(e2e_session, e2e_tenant_b)

        # 4. Enumerate and delete run-scoped Qdrant collections without suppression
        await cleanup_run_qdrant_collections(e2e_qdrant_client, e2e_run_id)

        # 5. Purge storage artifacts and verify
        cleanup_tenant_storage_artifacts(e2e_storage_root, e2e_tenant_a)
        cleanup_tenant_storage_artifacts(e2e_storage_root, e2e_tenant_b)
