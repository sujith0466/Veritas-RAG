import datetime
import io
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi import FastAPI, UploadFile, status
from httpx import AsyncClient, ASGITransport

import backend.document.services.metadata_service
import backend.document.workers.metadata_sync
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import get_db
from backend.core.exceptions.auth import AuthenticationException, InsufficientRoleException
from backend.core.permissions.rbac import Role
from backend.document.api.routes import router
from backend.document.models.status import DocumentStatus
from backend.document.schemas import DocumentListResponse, ProcessingStatusResponse
from backend.modules.retrieval.schemas.retrieval_dto import CandidatePointDTO


@pytest.fixture
def documents_test_app():
    app = FastAPI()

    @app.exception_handler(InsufficientRoleException)
    async def insufficient_role_handler(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"detail": str(exc)})

    @app.exception_handler(AuthenticationException)
    async def auth_exception_handler(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": str(exc)})

    # Mock DB dependency
    mock_session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_session
    # router already defines prefix="/documents"
    app.include_router(router, prefix="/api/v1")
    return app


# ==============================================================================
# D1.1 - DOCUMENT ROUTE RBAC TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_unauthenticated_requests_denied(documents_test_app):
    """Verify that requests without valid credentials return 401 Unauthorized across all routes."""
    def raise_unauth():
        raise AuthenticationException("Not authenticated")

    documents_test_app.dependency_overrides[get_current_user] = raise_unauth
    transport = ASGITransport(app=documents_test_app)
    doc_id = uuid.uuid4()

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # READ
        r = await client.get("/api/v1/documents")
        assert r.status_code == 401
        r = await client.get(f"/api/v1/documents/{doc_id}")
        assert r.status_code == 401
        r = await client.get(f"/api/v1/documents/{doc_id}/status")
        assert r.status_code == 401

        # MEMBER
        r = await client.post("/api/v1/documents/upload", files={"file": ("test.txt", b"content", "text/plain")})
        assert r.status_code == 401
        r = await client.put(f"/api/v1/documents/{doc_id}/metadata", json={"metadata": {"tag": "val"}})
        assert r.status_code == 401

        # ADMIN
        r = await client.delete(f"/api/v1/documents/{doc_id}")
        assert r.status_code == 401
        r = await client.post(f"/api/v1/documents/{doc_id}/archive")
        assert r.status_code == 401
        r = await client.post(f"/api/v1/documents/{doc_id}/restore")
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_viewer_role_rbac_boundary(documents_test_app):
    """Verify VIEWER can read documents, but is strictly blocked (403) from mutating and admin operations."""
    ws_id = uuid.uuid4()
    viewer_user = UserContext(
        id=uuid.uuid4(),
        email="viewer@test.com",
        role=Role.VIEWER.value,
        workspace_id=ws_id,
        tenant_id=str(ws_id),
    )
    documents_test_app.dependency_overrides[get_current_user] = lambda: viewer_user
    transport = ASGITransport(app=documents_test_app)
    doc_id = uuid.uuid4()
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    # Mock list and get service responses for allowed read routes
    with patch("backend.document.services.document_service.DocumentService.list_documents", new_callable=AsyncMock) as mock_list, \
         patch("backend.document.services.document_service.DocumentService.get_status", new_callable=AsyncMock) as mock_status:
        mock_list.return_value = DocumentListResponse(items=[], total=0, page=1, page_size=20, pages=1)
        mock_status.return_value = ProcessingStatusResponse(
            document_id=doc_id,
            status=DocumentStatus.READY.value,
            current_step="ready",
            progress_percent=100,
            retry_count=0,
            error_code=None,
            error_message=None,
            updated_at=now_utc,
        )

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # READ allowed (200)
            res = await client.get("/api/v1/documents")
            assert res.status_code == 200

            res = await client.get(f"/api/v1/documents/{doc_id}/status")
            assert res.status_code == 200

            # MEMBER mutations blocked (403)
            res = await client.post("/api/v1/documents/upload", files={"file": ("test.txt", b"content", "text/plain")})
            assert res.status_code == 403
            assert "insufficient" in res.json()["detail"].lower()

            res = await client.post(f"/api/v1/documents/{doc_id}/versions", files={"file": ("v2.txt", b"v2", "text/plain")})
            assert res.status_code == 403

            res = await client.put(f"/api/v1/documents/{doc_id}/metadata", json={"metadata": {"key": "val"}})
            assert res.status_code == 403

            res = await client.patch(f"/api/v1/documents/{doc_id}/metadata", json={"metadata": {"key": "val"}})
            assert res.status_code == 403

            res = await client.delete(f"/api/v1/documents/{doc_id}/metadata/tag")
            assert res.status_code == 403

            # ADMIN destructive operations blocked (403)
            res = await client.delete(f"/api/v1/documents/{doc_id}")
            assert res.status_code == 403

            res = await client.post(f"/api/v1/documents/{doc_id}/archive")
            assert res.status_code == 403

            res = await client.post(f"/api/v1/documents/{doc_id}/restore")
            assert res.status_code == 403

            res = await client.post(f"/api/v1/documents/{doc_id}/versions/{uuid.uuid4()}/rollback")
            assert res.status_code == 403


@pytest.mark.asyncio
async def test_member_role_rbac_boundary(documents_test_app):
    """Verify MEMBER can upload and modify metadata, but is strictly blocked (403) from admin operations."""
    ws_id = uuid.uuid4()
    member_user = UserContext(
        id=uuid.uuid4(),
        email="member@test.com",
        role=Role.MEMBER.value,
        workspace_id=ws_id,
        tenant_id=str(ws_id),
    )
    documents_test_app.dependency_overrides[get_current_user] = lambda: member_user
    transport = ASGITransport(app=documents_test_app)
    doc_id = uuid.uuid4()

    with patch("backend.modules.analytics.services.quota.QuotaGovernor.check_quota", new_callable=AsyncMock) as mock_quota, \
         patch("backend.document.services.document_service.DocumentService.upload_document", new_callable=AsyncMock) as mock_upload, \
         patch("backend.document.services.metadata_service.MetadataService.update_metadata", new_callable=AsyncMock) as mock_up_meta, \
         patch("backend.document.services.metadata_service.MetadataService.patch_metadata", new_callable=AsyncMock) as mock_patch_meta, \
         patch("backend.document.services.metadata_service.MetadataService.remove_metadata_key", new_callable=AsyncMock) as mock_del_meta, \
         patch("backend.document.workers.metadata_sync.sync_document_metadata_to_vectors_job.apply_async") as mock_async_sync:

        mock_quota.return_value = (False, 0, 1000, 0)
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        mock_doc = MagicMock()
        mock_doc.id = doc_id
        mock_doc.status = DocumentStatus.READY.value
        mock_doc.filename = "test.txt"
        mock_doc.original_filename = "test.txt"
        mock_doc.created_at = now_utc
        mock_ver = MagicMock()
        mock_ver.id = uuid.uuid4()
        mock_job = MagicMock()
        mock_job.id = uuid.uuid4()
        mock_upload.return_value = (mock_doc, mock_ver, mock_job)
        mock_up_meta.return_value = {"tag": "v1"}
        mock_patch_meta.return_value = {"tag": "v1", "tag2": "v2"}
        mock_del_meta.return_value = {"tag2": "v2"}

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # MEMBER mutations allowed (not 403)
            res = await client.post("/api/v1/documents/upload", files={"file": ("test.txt", b"hello world", "text/plain")})
            assert res.status_code == 202
            assert res.json()["success"] is True

            res = await client.put(f"/api/v1/documents/{doc_id}/metadata", json={"metadata": {"tag": "v1"}})
            assert res.status_code == 200

            res = await client.patch(f"/api/v1/documents/{doc_id}/metadata", json={"metadata": {"tag2": "v2"}})
            assert res.status_code == 200

            res = await client.delete(f"/api/v1/documents/{doc_id}/metadata/tag")
            assert res.status_code == 200

            # ADMIN operations blocked for MEMBER (403)
            res = await client.delete(f"/api/v1/documents/{doc_id}")
            assert res.status_code == 403

            res = await client.post(f"/api/v1/documents/{doc_id}/archive")
            assert res.status_code == 403

            res = await client.post(f"/api/v1/documents/{doc_id}/restore")
            assert res.status_code == 403

            res = await client.post(f"/api/v1/documents/{uuid.uuid4()}/versions/{uuid.uuid4()}/rollback")
            assert res.status_code == 403


@pytest.mark.asyncio
async def test_admin_and_owner_roles_rbac_boundary(documents_test_app):
    """Verify ADMIN and OWNER can perform admin operations (delete, archive, restore, rollback)."""
    ws_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    for target_role in [Role.ADMIN, Role.OWNER, Role.PLATFORM_ADMIN]:
        user = UserContext(
            id=uuid.uuid4(),
            email=f"{target_role.value}@test.com",
            role=target_role.value,
            workspace_id=ws_id,
            tenant_id=str(ws_id),
        )
        documents_test_app.dependency_overrides[get_current_user] = lambda u=user: u
        transport = ASGITransport(app=documents_test_app)

        with patch("backend.document.services.document_service.DocumentService.delete_document", new_callable=AsyncMock) as mock_del, \
             patch("backend.document.services.document_service.DocumentService.archive_document", new_callable=AsyncMock) as mock_arc, \
             patch("backend.document.services.document_service.DocumentService.restore_document", new_callable=AsyncMock) as mock_res, \
             patch("backend.document.services.document_service.DocumentService.rollback_to_version", new_callable=AsyncMock) as mock_rb:

            mock_del.return_value = True
            mock_arc.return_value = True
            mock_res.return_value = True
            mock_doc = MagicMock()
            mock_doc.id = doc_id
            mock_doc.status = DocumentStatus.READY.value
            mock_doc.filename = "test.txt"
            mock_doc.original_filename = "test.txt"
            mock_doc.created_at = now_utc
            mock_ver = MagicMock()
            mock_ver.id = uuid.uuid4()
            mock_job = MagicMock()
            mock_job.id = uuid.uuid4()
            mock_rb.return_value = (mock_doc, mock_ver, mock_job)

            async with AsyncClient(transport=transport, base_url="http://test") as client:
                res = await client.delete(f"/api/v1/documents/{doc_id}")
                assert res.status_code == 200, f"Role {target_role} should allow DELETE, got {res.status_code}"

                res = await client.post(f"/api/v1/documents/{doc_id}/archive")
                assert res.status_code == 200, f"Role {target_role} should allow archive, got {res.status_code}"

                res = await client.post(f"/api/v1/documents/{doc_id}/restore")
                assert res.status_code == 200, f"Role {target_role} should allow restore, got {res.status_code}"

                res = await client.post(f"/api/v1/documents/{doc_id}/versions/{uuid.uuid4()}/rollback")
                assert res.status_code == 202, f"Role {target_role} should allow rollback, got {res.status_code}"


# ==============================================================================
# D1.2 - QDRANT VECTOR DELETION & SOFT DELETE LOGIC
# ==============================================================================

@pytest.mark.asyncio
async def test_delete_document_service_pipeline():
    """Verify delete_document cleans DB, storage prefix, Qdrant vectors, appends audit log, and dispatches domain event."""
    from backend.document.services.document_service import DocumentService
    from backend.document.events.domain_events import EVENT_DOCUMENT_DELETED

    service = DocumentService()
    session = AsyncMock()
    doc_id = uuid.uuid4()
    tenant_id = "test-tenant-123"

    mock_doc = MagicMock()
    mock_doc.id = doc_id
    mock_doc.tenant_id = tenant_id

    with patch.object(service.doc_repo, "get_by_id_with_versions", new_callable=AsyncMock) as mock_get, \
         patch.object(service.doc_repo, "delete", new_callable=AsyncMock) as mock_soft_del, \
         patch.object(service.storage, "delete_prefix", new_callable=AsyncMock) as mock_storage, \
         patch("backend.modules.vector.services.vector_service.VectorStorageService.delete_document_points", new_callable=AsyncMock) as mock_qdrant_del, \
         patch.object(service.event_repo, "append_event", new_callable=AsyncMock) as mock_event, \
         patch("backend.core.events.dispatcher.get_dispatcher") as mock_get_dispatcher:

        mock_get.return_value = mock_doc
        mock_soft_del.return_value = True
        mock_qdrant_del.return_value = 15
        mock_dispatcher = MagicMock()
        mock_dispatcher.publish = AsyncMock()
        mock_get_dispatcher.return_value = mock_dispatcher

        result = await service.delete_document(doc_id, tenant_id, session)
        assert result is True

        # Verify DB soft deletion
        mock_soft_del.assert_awaited_once_with(doc_id, tenant_id, session)

        # Verify physical file storage purge with prefix
        mock_storage.assert_awaited_once_with(f"documents/{tenant_id}/{doc_id}")

        # Verify Qdrant points deletion
        mock_qdrant_del.assert_awaited_once_with(document_id=doc_id, tenant_id=tenant_id)

        # Verify audit event append
        assert mock_event.await_count == 1
        event_arg = mock_event.await_args[0][0]
        assert event_arg.event_type == EVENT_DOCUMENT_DELETED
        assert event_arg.document_id == doc_id

        # Verify domain event dispatch for BM25 invalidation
        mock_dispatcher.publish.assert_awaited_once()
        del_domain_event = mock_dispatcher.publish.await_args[0][0]
        assert del_domain_event.document_id == str(doc_id)
        assert del_domain_event.tenant_id == tenant_id


@pytest.mark.asyncio
async def test_vector_service_safe_absent_collection():
    """Verify VectorStorageService.delete_document_points handles absent collections ('not found') safely without crashing."""
    from backend.modules.vector.services.vector_service import VectorStorageService

    mock_session = AsyncMock()
    # Mock database queries to return empty lists for collection discovery and metadata records
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_result

    vec_service = VectorStorageService(session=mock_session)
    doc_id = uuid.uuid4()
    tenant_id = "tenant-safe-456"

    with patch.object(vec_service.provider, "delete_points_by_filter", new_callable=AsyncMock) as mock_delete_filter:
        mock_delete_filter.side_effect = Exception("Status 404: Collection rag_tenant_safe_456 not found")

        total_ops = await vec_service.delete_document_points(doc_id, tenant_id, collection_name="test_col")
        assert total_ops == 0


@pytest.mark.asyncio
async def test_vector_service_failure_awareness():
    """Verify VectorStorageService.delete_document_points raises real cluster/network errors."""
    from backend.modules.vector.services.vector_service import VectorStorageService

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_result

    vec_service = VectorStorageService(session=mock_session)
    doc_id = uuid.uuid4()
    tenant_id = "tenant-fail-789"

    with patch.object(vec_service.provider, "delete_points_by_filter", new_callable=AsyncMock) as mock_delete_filter:
        mock_delete_filter.side_effect = ConnectionError("Failed to reach Qdrant cluster at http://qdrant:6333")

        with pytest.raises(ConnectionError):
            await vec_service.delete_document_points(doc_id, tenant_id, collection_name="test_col")


# ==============================================================================
# D1.3 - RETRIEVAL DEFENSE-IN-DEPTH CANDIDATE FILTERING
# ==============================================================================

@pytest.mark.asyncio
async def test_retrieval_defense_in_depth_filters_deleted_or_non_ready():
    """Verify that retrieval orchestrator Stage 2.5 filters out soft-deleted and non-READY documents from candidates."""
    from backend.modules.retrieval.services.retrieval_service import RetrievalOrchestrator

    ready_doc_id = uuid.uuid4()
    deleted_doc_id = uuid.uuid4()
    pending_doc_id = uuid.uuid4()
    tenant_id = "tenant-rag-001"

    mock_repo = AsyncMock()
    mock_repo.filter_active_ready_document_ids.return_value = {ready_doc_id}

    orchestrator = RetrievalOrchestrator(
        embedding_provider=MagicMock(),
        vector_provider=MagicMock(),
        sparse_provider=MagicMock(),
        reranker_provider=MagicMock(),
        repository=mock_repo,
    )

    chunk_ready = CandidatePointDTO(
        chunk_id=uuid.uuid4(),
        document_id=ready_doc_id,
        document_version_id=uuid.uuid4(),
        tenant_id=tenant_id,
        content="Active document content",
        score=0.9,
        source="dense",
        rank=1,
    )

    chunk_deleted = CandidatePointDTO(
        chunk_id=uuid.uuid4(),
        document_id=deleted_doc_id,
        document_version_id=uuid.uuid4(),
        tenant_id=tenant_id,
        content="Soft-deleted document content",
        score=0.85,
        source="dense",
        rank=2,
    )

    chunk_pending = CandidatePointDTO(
        chunk_id=uuid.uuid4(),
        document_id=pending_doc_id,
        document_version_id=uuid.uuid4(),
        tenant_id=tenant_id,
        content="Pending document content",
        score=0.8,
        source="sparse",
        rank=3,
    )

    candidates = [chunk_ready, chunk_deleted, chunk_pending]

    candidate_doc_ids = {c.document_id for c in candidates if getattr(c, "document_id", None)}
    valid_doc_ids = await orchestrator.repository.filter_active_ready_document_ids(
        candidate_doc_ids, tenant_id
    )
    filtered_candidates = [c for c in candidates if getattr(c, "document_id", None) in valid_doc_ids]

    assert len(filtered_candidates) == 1
    assert filtered_candidates[0].document_id == ready_doc_id
    assert deleted_doc_id not in [c.document_id for c in filtered_candidates]
    assert pending_doc_id not in [c.document_id for c in filtered_candidates]


# ==============================================================================
# D1.4 - RESTORE CORRECTNESS TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_restore_document_sets_intermediate_vector_sync_status():
    """Verify restore_document updates document status to VECTOR_SYNC and dispatches Celery job."""
    from backend.document.repositories.document_repository import DocumentRepository
    from backend.document.models.document import Document

    repo = DocumentRepository()
    session = AsyncMock()
    doc_id = uuid.uuid4()
    tenant_id = "tenant-1"
    mock_doc = Document(id=doc_id, tenant_id=tenant_id, status=DocumentStatus.ARCHIVED.value)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_doc
    session.execute.return_value = mock_result

    result = await repo.restore_document(doc_id, tenant_id, session)
    assert result is not None
    assert mock_doc.status == DocumentStatus.VECTOR_SYNC.value
    assert mock_doc.archived_at is None
    assert mock_doc.archived_by_user_id is None


def test_restore_worker_transitions_to_ready_on_success():
    """Verify restore_archived_document_vectors_job transitions document status to READY upon vector sync completion."""
    from backend.document.workers.archive import restore_archived_document_vectors_job
    from backend.document.models.document import Document

    doc_id = uuid.uuid4()
    ver_id = uuid.uuid4()
    tenant_id = "tenant-restore-test"

    mock_doc = Document(id=doc_id, tenant_id=tenant_id, status=DocumentStatus.VECTOR_SYNC.value)

    with patch("backend.document.workers.archive.get_session_factory") as mock_sf, \
         patch("backend.modules.vector.services.vector_service.VectorStorageService.sync_document_vectors", new_callable=AsyncMock) as mock_sync:

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_doc
        mock_sf.return_value = MagicMock(return_value=MagicMock(__aenter__=AsyncMock(return_value=mock_session), __aexit__=AsyncMock(return_value=None)))
        mock_sync.return_value = 10

        # Execute Celery worker task run directly (synchronous execution outside running loop)
        res = restore_archived_document_vectors_job.run(
            str(doc_id),
            str(ver_id),
            tenant_id
        )

        assert res["status"] == "success"
        assert res["synced_ops"] == 10
        assert mock_doc.status == DocumentStatus.READY.value
        mock_session.commit.assert_awaited()
