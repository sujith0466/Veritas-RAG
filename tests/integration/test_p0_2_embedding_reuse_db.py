"""Database-backed integration test for P0-2: Embedding Reuse Correctness.

Verifies against `raguard_test_db` only:
1. Baseline embedding creation.
2. Fully cached document version with duplicate content hashes and zero provider calls.
3. Partially cached document version with novel chunks.
4. Stale dimension-mismatch fallback to active provider with current dimension.
5. Invariant integrity: tenant_id, chunk_id, document_version_id, dimensions, vectors, active counts.
6. Visibility through the production vector-sync query (vector_service.py:79-84).
7. Strict transaction rollback isolation and credential redaction.
"""

from collections.abc import AsyncGenerator
import os
from typing import Any
from unittest.mock import AsyncMock, patch
from urllib.parse import urlparse
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.core.config import get_settings
from backend.core.events.dispatcher import EventDispatcher
from backend.document.models.document import Document, DocumentVersion
from backend.document.models.storage_object import StorageObject
from backend.modules.chunking.models.chunk import DocumentChunk
from backend.modules.embedding.models.chunk_embedding import ChunkEmbedding
from backend.modules.embedding.models.embedding_job import EmbeddingJob
from backend.modules.embedding.providers.factory import register_provider
from backend.modules.embedding.providers.local_provider import LocalEmbeddingProvider
from backend.modules.embedding.repositories.embedding_repository import EmbeddingRepository
from backend.modules.embedding.services.embedding_service import EmbeddingService


def _redact_url(url: str) -> str:
    parsed = urlparse(url)
    netloc = parsed.netloc.split("@")[-1] if "@" in parsed.netloc else parsed.netloc
    return f"{parsed.scheme}://***:***@{netloc}{parsed.path}"


class DeterministicOfflineProvider(LocalEmbeddingProvider):
    """Offline local provider generating 384-dimensional vectors deterministically."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(model_name="BAAI/bge-small-en-v1.5", offline=True)


@pytest.fixture(autouse=True)
def register_deterministic_provider() -> None:
    register_provider("local", DeterministicOfflineProvider)


@pytest_asyncio.fixture
async def verified_test_engine():
    """Verify target database is strictly 'raguard_test_db' before yielding engine."""
    get_settings.cache_clear()
    settings = get_settings()
    db_url = settings.database.url

    assert "raguard_test_db" in db_url, (
        f"CRITICAL SAFETY VIOLATION: DATABASE_URL must explicitly target 'raguard_test_db'. "
        f"Configured target: {_redact_url(db_url)}"
    )

    engine = create_async_engine(db_url, echo=False)
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT current_database();"))
        actual_db = res.scalar()
        assert actual_db == "raguard_test_db", (
            f"CRITICAL SAFETY VIOLATION: Connected database is '{actual_db}'. "
            "Execution is strictly restricted to 'raguard_test_db'."
        )

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(verified_test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session inside an outer transaction that rolls back automatically."""
    async with verified_test_engine.connect() as connection:
        transaction = await connection.begin()
        session_maker = async_sessionmaker(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        session = session_maker()
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


@pytest.mark.asyncio
async def test_p0_2_embedding_reuse_database_backed(db_session: AsyncSession) -> None:
    """Execute complete database-backed verification for P0-2 embedding reuse correctness."""
    # 0. Safety confirmation within the active session
    res = await db_session.execute(text("SELECT current_database();"))
    assert res.scalar() == "raguard_test_db", "Execution must occur inside 'raguard_test_db'"

    tenant_id = f"test_p02_{uuid.uuid4().hex[:12]}"
    mock_dispatcher = AsyncMock(spec=EventDispatcher)
    repo = EmbeddingRepository(db_session)
    service = EmbeddingService(repository=repo, event_dispatcher=mock_dispatcher)

    # 1. Seed Shared Storage Object & Document Root
    so = StorageObject(
        id=uuid.uuid4(),
        provider="local",
        bucket_or_container="test-bucket",
        object_key=f"p02_test_{uuid.uuid4().hex}.txt",
        file_size_bytes=2048,
        mime_type="text/plain",
        checksum_sha256="dummy_sha256_hash",
    )
    doc_id = uuid.uuid4()
    await db_session.execute(
        text("""
            INSERT INTO documents (
                id, tenant_id, filename, original_filename, status, word_count, page_count, user_metadata, is_deleted, created_at, updated_at
            )
            VALUES (:id, :tenant_id, :filename, :original_filename, :status, 0, 0, '{}'::jsonb, false, NOW(), NOW())
        """),
        {
            "id": doc_id,
            "tenant_id": tenant_id,
            "filename": "contract.pdf",
            "original_filename": "contract.pdf",
            "status": "PROCESSING",
        },
    )
    db_session.add(so)
    await db_session.flush()

    # 2. Seed Baseline Version 1 (2 Chunks: alpha and beta)
    v1 = DocumentVersion(
        id=uuid.uuid4(),
        document_id=doc_id,
        version_number=1,
        storage_object_id=so.id,
        content_hash="v1_hash",
        is_active_vector=True,
    )
    db_session.add(v1)
    await db_session.flush()

    c1_v1 = DocumentChunk(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        document_id=doc_id,
        document_version_id=v1.id,
        chunk_index=0,
        content="Alpha terms and conditions paragraph",
        content_hash="hash_alpha",
        strategy_used="hierarchical",
        is_embedded=False,
    )
    c2_v1 = DocumentChunk(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        document_id=doc_id,
        document_version_id=v1.id,
        chunk_index=1,
        content="Beta warranty and liability terms",
        content_hash="hash_beta",
        strategy_used="hierarchical",
        is_embedded=False,
    )
    db_session.add_all([c1_v1, c2_v1])
    await db_session.flush()

    # Create & Process Embedding Job for Version 1
    job_v1 = EmbeddingJob(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        document_id=doc_id,
        document_version_id=v1.id,
        status="PENDING",
        provider="local",
        model_name="BAAI/bge-small-en-v1.5",
        total_chunks=2,
        processed_chunks=0,
    )
    db_session.add(job_v1)
    await db_session.flush()

    with patch("backend.cache.rate_limit.RateLimiter.check_limit", return_value={"current": 1, "limit": 600, "remaining": 599}):
        completed_v1 = await service.process_embedding_batch(job_id=job_v1.id, tenant_id=tenant_id)
        assert completed_v1.status == "COMPLETED"
        assert completed_v1.processed_chunks == 2

    # Verify Version 1 database state
    v1_embeddings_stmt = select(ChunkEmbedding).where(
        ChunkEmbedding.tenant_id == tenant_id,
        ChunkEmbedding.document_version_id == v1.id,
        ChunkEmbedding.is_deleted.is_(False),
    )
    v1_recs = (await db_session.execute(v1_embeddings_stmt)).scalars().all()
    assert len(v1_recs) == 2
    assert all(r.dimension == 384 for r in v1_recs)
    assert all(isinstance(r.embedding_vector, list) and len(r.embedding_vector) == 384 for r in v1_recs)

    # 3. Seed Fully Cached Version 2 (3 Chunks: alpha, beta, and duplicate alpha)
    v2 = DocumentVersion(
        id=uuid.uuid4(),
        document_id=doc_id,
        version_number=2,
        storage_object_id=so.id,
        content_hash="v2_hash",
        is_active_vector=True,
    )
    db_session.add(v2)
    await db_session.flush()

    c1_v2 = DocumentChunk(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        document_id=doc_id,
        document_version_id=v2.id,
        chunk_index=0,
        content="Alpha terms and conditions paragraph",
        content_hash="hash_alpha",  # Cache hit
        strategy_used="hierarchical",
        is_embedded=False,
    )
    c2_v2 = DocumentChunk(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        document_id=doc_id,
        document_version_id=v2.id,
        chunk_index=1,
        content="Beta warranty and liability terms",
        content_hash="hash_beta",  # Cache hit
        strategy_used="hierarchical",
        is_embedded=False,
    )
    c3_v2 = DocumentChunk(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        document_id=doc_id,
        document_version_id=v2.id,
        chunk_index=2,
        content="Alpha terms and conditions paragraph",
        content_hash="hash_alpha",  # Duplicate content hash in same version!
        strategy_used="hierarchical",
        is_embedded=False,
    )
    db_session.add_all([c1_v2, c2_v2, c3_v2])
    await db_session.flush()

    job_v2 = EmbeddingJob(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        document_id=doc_id,
        document_version_id=v2.id,
        status="PENDING",
        provider="local",
        model_name="BAAI/bge-small-en-v1.5",
        total_chunks=3,
        processed_chunks=0,
    )
    db_session.add(job_v2)
    await db_session.flush()

    # Process Version 2 with SPY asserting ZERO provider vectorize calls
    with patch(
        "backend.modules.embedding.services.embedding_service.EmbeddingManager.vectorize_batch"
    ) as mock_vectorize, patch(
        "backend.cache.rate_limit.RateLimiter.check_limit",
        return_value={"current": 1, "limit": 600, "remaining": 599},
    ):
        completed_v2 = await service.process_embedding_batch(job_id=job_v2.id, tenant_id=tenant_id)
        assert completed_v2.status == "COMPLETED"
        assert completed_v2.processed_chunks == 3
        # Invariant 4: Zero provider calls on fully cached version
        mock_vectorize.assert_not_called()

    # Verify Version 2 in real PostgreSQL database
    v2_embeddings_stmt = select(ChunkEmbedding).where(
        ChunkEmbedding.tenant_id == tenant_id,
        ChunkEmbedding.document_version_id == v2.id,
        ChunkEmbedding.is_deleted.is_(False),
    ).order_by(ChunkEmbedding.created_at.asc())
    v2_recs = (await db_session.execute(v2_embeddings_stmt)).scalars().all()

    # Invariant 1: Exactly 3 records created for current version
    assert len(v2_recs) == 3

    # Invariant 2 & 5: Bound to current version with correct tenant, dimension, vector
    assert all(r.document_version_id == v2.id for r in v2_recs)
    assert all(r.tenant_id == tenant_id for r in v2_recs)
    assert all(r.dimension == 384 for r in v2_recs)
    assert all(isinstance(r.embedding_vector, list) and len(r.embedding_vector) == 384 for r in v2_recs)

    # Invariant 3: Distinct chunk IDs and duplicate hash handling
    staged_chunk_ids = {r.chunk_id for r in v2_recs}
    assert staged_chunk_ids == {c1_v2.id, c2_v2.id, c3_v2.id}
    alpha_recs = [r for r in v2_recs if r.content_hash == "hash_alpha"]
    assert len(alpha_recs) == 2
    assert alpha_recs[0].chunk_id != alpha_recs[1].chunk_id
    assert {alpha_recs[0].chunk_id, alpha_recs[1].chunk_id} == {c1_v2.id, c3_v2.id}

    # Verify production Vector-Sync Query Visibility (vector_service.py:79-84)
    sync_emb_stmt = select(ChunkEmbedding).where(
        ChunkEmbedding.tenant_id == tenant_id,
        ChunkEmbedding.document_version_id == v2.id,
        ChunkEmbedding.is_deleted.is_(False),
    )
    sync_recs = (await db_session.execute(sync_emb_stmt)).scalars().all()
    assert len(sync_recs) == 3

    # 4. Seed Partially Cached Version 3 with Stale Dimension Mismatch
    # Create legacy chunk with mismatched dimension (768) in historical version
    c_legacy = DocumentChunk(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        document_id=doc_id,
        document_version_id=v1.id,
        chunk_index=99,
        content="Mismatched legacy dimension text",
        content_hash="hash_mismatch",
        strategy_used="hierarchical",
        is_embedded=True,
    )
    db_session.add(c_legacy)
    await db_session.flush()

    emb_legacy = ChunkEmbedding(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        chunk_id=c_legacy.id,
        document_version_id=v1.id,
        content_hash="hash_mismatch",
        provider="local",
        model_name="BAAI/bge-small-en-v1.5",
        dimension=768,  # Mismatched dimension!
        embedding_vector=[0.7] * 768,
    )
    db_session.add(emb_legacy)
    await db_session.flush()

    # Create Version 3
    v3 = DocumentVersion(
        id=uuid.uuid4(),
        document_id=doc_id,
        version_number=3,
        storage_object_id=so.id,
        content_hash="v3_hash",
        is_active_vector=True,
    )
    db_session.add(v3)
    await db_session.flush()

    # Version 3 Chunks:
    # Chunk A: hash_alpha (Valid 384 cache hit)
    # Chunk B: hash_novel (Novel cache miss)
    # Chunk C: hash_mismatch (Dimension mismatch: 768 in cache, manager expects 384)
    c1_v3 = DocumentChunk(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        document_id=doc_id,
        document_version_id=v3.id,
        chunk_index=0,
        content="Alpha terms and conditions paragraph",
        content_hash="hash_alpha",
        strategy_used="hierarchical",
        is_embedded=False,
    )
    c2_v3 = DocumentChunk(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        document_id=doc_id,
        document_version_id=v3.id,
        chunk_index=1,
        content="Completely brand new text clause",
        content_hash="hash_novel",
        strategy_used="hierarchical",
        is_embedded=False,
    )
    c3_v3 = DocumentChunk(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        document_id=doc_id,
        document_version_id=v3.id,
        chunk_index=2,
        content="Mismatched legacy dimension text",
        content_hash="hash_mismatch",
        strategy_used="hierarchical",
        is_embedded=False,
    )
    db_session.add_all([c1_v3, c2_v3, c3_v3])
    await db_session.flush()

    job_v3 = EmbeddingJob(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        document_id=doc_id,
        document_version_id=v3.id,
        status="PENDING",
        provider="local",
        model_name="BAAI/bge-small-en-v1.5",
        total_chunks=3,
        processed_chunks=0,
    )
    db_session.add(job_v3)
    await db_session.flush()

    with patch(
        "backend.cache.rate_limit.RateLimiter.check_limit",
        return_value={"current": 1, "limit": 600, "remaining": 599},
    ):
        completed_v3 = await service.process_embedding_batch(job_id=job_v3.id, tenant_id=tenant_id)
        assert completed_v3.status == "COMPLETED"
        assert completed_v3.processed_chunks == 3

    # Verify Version 3 in database
    v3_embeddings_stmt = select(ChunkEmbedding).where(
        ChunkEmbedding.tenant_id == tenant_id,
        ChunkEmbedding.document_version_id == v3.id,
        ChunkEmbedding.is_deleted.is_(False),
    )
    v3_recs = (await db_session.execute(v3_embeddings_stmt)).scalars().all()
    assert len(v3_recs) == 3

    # All Version 3 records must have valid 384 dimension (including fallback for c3_v3)
    assert all(r.dimension == 384 for r in v3_recs)
    assert all(isinstance(r.embedding_vector, list) and len(r.embedding_vector) == 384 for r in v3_recs)

    mismatch_rec = next(r for r in v3_recs if r.chunk_id == c3_v3.id)
    assert mismatch_rec.dimension == 384
    assert len(mismatch_rec.embedding_vector) == 384

    # Vector-Sync Query Visibility for Version 3
    sync_v3_recs = (await db_session.execute(
        select(ChunkEmbedding).where(
            ChunkEmbedding.tenant_id == tenant_id,
            ChunkEmbedding.document_version_id == v3.id,
            ChunkEmbedding.is_deleted.is_(False),
        )
    )).scalars().all()
    assert len(sync_v3_recs) == 3
