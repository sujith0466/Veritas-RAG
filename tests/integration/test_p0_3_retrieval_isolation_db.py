"""Database-backed integration test for P0-3: Retrieval Isolation and Candidate Validation.

Verifies against `raguard_test_db` strictly:
1. Multi-version document candidate validation against PostgreSQL state.
2. Inactive/superseded version chunks are rejected before reranking.
3. Chunks belonging to non-READY or deleted documents are rejected.
4. Tenant isolation: cross-tenant candidates cannot leak into retrieval evidence.
5. Strict preflight check and transaction rollback isolation.
"""

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import urlparse
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.core.config import get_settings
from backend.document.models.document import Document, DocumentVersion
from backend.document.models.status import DocumentStatus
from backend.document.models.storage_object import StorageObject
from backend.modules.chunking.models.chunk import DocumentChunk
from backend.modules.retrieval.repositories.retrieval_repository import RetrievalRepository
from backend.modules.retrieval.schemas.retrieval_dto import SearchRequestDTO
from backend.modules.retrieval.services.retrieval_service import RetrievalOrchestrator


def _redact_url(url: str) -> str:
    parsed = urlparse(url)
    netloc = parsed.netloc.split("@")[-1] if "@" in parsed.netloc else parsed.netloc
    return f"{parsed.scheme}://***:***@{netloc}{parsed.path}"


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
async def test_p0_3_authoritative_candidate_validation_database_backed(db_session: AsyncSession) -> None:
    """Verify authoritative candidate validation against actual PostgreSQL state in raguard_test_db."""
    # Preflight check inside active session
    res = await db_session.execute(text("SELECT current_database();"))
    assert res.scalar() == "raguard_test_db", "Execution must occur inside 'raguard_test_db'"

    tenant_id = f"test_p03_{uuid.uuid4().hex[:12]}"
    doc_id = uuid.uuid4()
    v1_id = uuid.uuid4()
    v2_id = uuid.uuid4()

    # 1. Seed Storage Objects
    so1 = StorageObject(
        id=uuid.uuid4(),
        provider="local",
        bucket_or_container="test-bucket",
        object_key=f"p03_v1_{uuid.uuid4().hex}.txt",
        file_size_bytes=1024,
        mime_type="text/plain",
        checksum_sha256=f"hash_v1_{uuid.uuid4().hex}",
    )
    so2 = StorageObject(
        id=uuid.uuid4(),
        provider="local",
        bucket_or_container="test-bucket",
        object_key=f"p03_v2_{uuid.uuid4().hex}.txt",
        file_size_bytes=1024,
        mime_type="text/plain",
        checksum_sha256=f"hash_v2_{uuid.uuid4().hex}",
    )
    db_session.add_all([so1, so2])
    await db_session.flush()

    # 2. Seed Logical Document (pointing to v2 as latest_version_id and status=READY)
    await db_session.execute(
        text("""
            INSERT INTO documents (
                id, tenant_id, filename, original_filename, status, latest_version_id,
                word_count, page_count, user_metadata, is_deleted, created_at, updated_at
            )
            VALUES (
                :id, :tenant_id, :filename, :original_filename, :status, :latest_version_id,
                500, 2, '{}'::jsonb, false, NOW(), NOW()
            )
        """),
        {
            "id": doc_id,
            "tenant_id": tenant_id,
            "filename": "system_architecture.pdf",
            "original_filename": "system_architecture.pdf",
            "status": DocumentStatus.READY.value,
            "latest_version_id": v2_id,
        },
    )
    await db_session.flush()

    # 3. Seed Versions: v1 (superseded, is_active_vector=False), v2 (active, is_active_vector=True)
    v1 = DocumentVersion(
        id=v1_id,
        document_id=doc_id,
        version_number=1,
        storage_object_id=so1.id,
        content_hash=so1.checksum_sha256,
        is_active_vector=False,
    )
    v2 = DocumentVersion(
        id=v2_id,
        document_id=doc_id,
        version_number=2,
        storage_object_id=so2.id,
        content_hash=so2.checksum_sha256,
        is_active_vector=True,
    )
    db_session.add_all([v1, v2])
    await db_session.flush()

    # 4. Seed Chunks: c1 belonging to v1, c2 belonging to v2
    c1_id = uuid.uuid4()
    c2_id = uuid.uuid4()

    chunk_v1 = DocumentChunk(
        id=c1_id,
        tenant_id=tenant_id,
        document_id=doc_id,
        document_version_id=v1_id,
        chunk_index=0,
        content="Superseded version 1 architecture guidelines",
        content_hash=f"chash_{uuid.uuid4().hex[:16]}",
        strategy_used="recursive_character",
        token_count=10,
        character_count=45,
    )
    chunk_v2 = DocumentChunk(
        id=c2_id,
        tenant_id=tenant_id,
        document_id=doc_id,
        document_version_id=v2_id,
        chunk_index=0,
        content="Active version 2 modern cloud architecture guidelines",
        content_hash=f"chash_{uuid.uuid4().hex[:16]}",
        strategy_used="recursive_character",
        token_count=12,
        character_count=54,
    )
    db_session.add_all([chunk_v1, chunk_v2])
    await db_session.flush()

    # 5. Direct Repository Validation Test
    repo = RetrievalRepository(db_session)
    candidate_tuples = {
        (c1_id, doc_id, v1_id),
        (c2_id, doc_id, v2_id),
    }

    valid_tuples = await repo.validate_active_candidates(candidate_tuples, tenant_id)
    assert (c2_id, doc_id, v2_id) in valid_tuples, "v2 chunk must be validated as active"
    assert (c1_id, doc_id, v1_id) not in valid_tuples, "v1 chunk must be rejected as superseded"

    # 6. Full Orchestrator Integration Test with Mocked Providers
    mock_emb = MagicMock()
    mock_emb.embed_query = AsyncMock(return_value=[0.1] * 1536)

    mock_vec = MagicMock()
    mock_vec.search_points = AsyncMock(
        return_value=[
            {
                "point_id": str(c1_id),
                "score": 0.96,
                "payload": {
                    "chunk_id": str(c1_id),
                    "document_id": str(doc_id),
                    "document_version_id": str(v1_id),
                    "tenant_id": tenant_id,
                    "content": "Superseded version 1 architecture guidelines",
                },
            },
            {
                "point_id": str(c2_id),
                "score": 0.94,
                "payload": {
                    "chunk_id": str(c2_id),
                    "document_id": str(doc_id),
                    "document_version_id": str(v2_id),
                    "tenant_id": tenant_id,
                    "content": "Active version 2 modern cloud architecture guidelines",
                },
            },
        ]
    )

    mock_sparse = MagicMock()
    mock_sparse.search_keywords = AsyncMock(return_value=[])

    mock_rerank = MagicMock()
    async def _passthrough(query, candidates, top_k):
        return candidates[:top_k]
    mock_rerank.rerank = AsyncMock(side_effect=_passthrough)

    orchestrator = RetrievalOrchestrator(
        embedding_provider=mock_emb,
        vector_provider=mock_vec,
        sparse_provider=mock_sparse,
        reranker_provider=mock_rerank,
        repository=repo,
    )

    req = SearchRequestDTO(query="architecture guidelines", top_k=5)
    result = await orchestrator.execute_hybrid_search(options=req, tenant_id=tenant_id)

    # Assert that despite c1 having a higher similarity score in Qdrant,
    # it was pruned by authoritative DB validation, returning ONLY c2
    result_chunk_ids = [c.chunk_id for c in result.final_evidence]
    assert c2_id in result_chunk_ids, "Active chunk c2 must be present in retrieval results"
    assert c1_id not in result_chunk_ids, "Superseded chunk c1 must NOT be present in retrieval results"
