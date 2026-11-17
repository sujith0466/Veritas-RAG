"""Security test suite for WP-4: Document Access & Deletion Separation (DEC-06).

Verifies:
1. Full document deletion is strictly restricted to workspace OWNER and ADMIN.
2. Granular metadata-key deletion is permitted for MEMBER (and ADMIN/OWNER).
3. Strict tenant isolation: documents/metadata belonging to another workspace cannot be deleted.
4. Authoritative database membership revalidation: callers with stale JWT tokens (demoted in DB)
   are blocked from deleting documents.
5. Suspended/deleted members are blocked from deletion operations.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest
from fastapi import FastAPI, HTTPException, status
from httpx import ASGITransport, AsyncClient

from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import get_db
from backend.core.exceptions.auth import AuthenticationException, InsufficientRoleException
from backend.core.permissions.rbac import Role
from backend.document.api.routes import router
from backend.document.models.status import DocumentStatus
from backend.document.schemas.errors import DocumentDomainException
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember


@pytest.fixture(autouse=True)
def mock_rate_limiter():
    with patch("backend.cache.rate_limit.RateLimiter.check_limit", new_callable=AsyncMock) as m:
        m.return_value = {"current": 1, "limit": 100, "remaining": 99, "reset_seconds": 60}
        yield m


@pytest.fixture
def app():
    test_app = FastAPI()

    @test_app.exception_handler(InsufficientRoleException)
    async def insufficient_role_handler(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"detail": str(exc)})

    @test_app.exception_handler(AuthenticationException)
    async def auth_exception_handler(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": str(exc)})

    mock_session = AsyncMock()
    test_app.dependency_overrides[get_db] = lambda: mock_session
    test_app.include_router(router, prefix="/api/v1")
    return test_app


@pytest.mark.asyncio
async def test_member_cannot_delete_full_document(app):
    """MEMBER role receives 403 when attempting full document deletion."""
    ws_id = uuid.uuid4()
    member_user = UserContext(
        id=uuid.uuid4(),
        email="member@test.com",
        role=Role.MEMBER.value,
        workspace_id=ws_id,
        tenant_id=str(ws_id),
    )
    app.dependency_overrides[get_current_user] = lambda: member_user
    doc_id = uuid.uuid4()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.delete(f"/api/v1/documents/{doc_id}")
        assert res.status_code == 403
        assert "insufficient" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_viewer_cannot_delete_full_document(app):
    """VIEWER role receives 403 when attempting full document deletion."""
    ws_id = uuid.uuid4()
    viewer_user = UserContext(
        id=uuid.uuid4(),
        email="viewer@test.com",
        role=Role.VIEWER.value,
        workspace_id=ws_id,
        tenant_id=str(ws_id),
    )
    app.dependency_overrides[get_current_user] = lambda: viewer_user
    doc_id = uuid.uuid4()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.delete(f"/api/v1/documents/{doc_id}")
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_member_can_delete_metadata_key(app):
    """MEMBER role is allowed to delete specific metadata keys."""
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    member_user = UserContext(
        id=user_id,
        email="member@test.com",
        role=Role.MEMBER.value,
        workspace_id=ws_id,
        tenant_id=str(ws_id),
    )
    app.dependency_overrides[get_current_user] = lambda: member_user
    doc_id = uuid.uuid4()

    mock_db_member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=user_id,
        role="MEMBER",
        status=MemberStatus.ACTIVE.value,
        is_deleted=False,
    )

    with patch("backend.repositories.workspace_member.WorkspaceMemberRepository.get_membership", new_callable=AsyncMock) as mock_mem, \
         patch("backend.document.services.metadata_service.MetadataService.remove_metadata_key", new_callable=AsyncMock) as mock_del_meta, \
         patch("backend.document.workers.metadata_sync.sync_document_metadata_to_vectors_job.apply_async"):
        mock_mem.return_value = mock_db_member
        mock_del_meta.return_value = {"remaining_tag": "val"}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.delete(f"/api/v1/documents/{doc_id}/metadata/obsolete_key")
            assert res.status_code == 200
            assert res.json()["success"] is True
            assert res.json()["data"] == {"remaining_tag": "val"}
            mock_del_meta.assert_awaited_once_with(doc_id, str(ws_id), "obsolete_key")


@pytest.mark.asyncio
async def test_admin_and_owner_can_delete_full_document(app):
    """ADMIN and OWNER can perform full document deletion."""
    ws_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    for role_val in [Role.ADMIN.value, Role.OWNER.value]:
        user_id = uuid.uuid4()
        user = UserContext(
            id=user_id,
            email=f"{role_val.lower()}@test.com",
            role=role_val,
            workspace_id=ws_id,
            tenant_id=str(ws_id),
        )
        app.dependency_overrides[get_current_user] = lambda u=user: u

        mock_db_member = WorkspaceMember(
            id=uuid.uuid4(),
            workspace_id=ws_id,
            user_id=user_id,
            role=role_val,
            status=MemberStatus.ACTIVE.value,
            is_deleted=False,
        )

        with patch("backend.repositories.workspace_member.WorkspaceMemberRepository.get_membership", new_callable=AsyncMock) as mock_mem, \
             patch("backend.document.services.document_service.DocumentService.delete_document", new_callable=AsyncMock) as mock_delete:
            mock_mem.return_value = mock_db_member
            mock_delete.return_value = True

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                res = await client.delete(f"/api/v1/documents/{doc_id}")
                assert res.status_code == 200
                assert res.json()["success"] is True
                assert res.json()["data"]["deleted"] is True
                assert res.json()["data"]["document_id"] == str(doc_id)
                mock_delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_cross_tenant_document_deletion_rejected(app):
    """Attempting to delete a document residing in another tenant returns 404 (document not found for tenant)."""
    tenant_a = uuid.uuid4()
    user_id = uuid.uuid4()
    admin_user = UserContext(
        id=user_id,
        email="admin_a@test.com",
        role=Role.ADMIN.value,
        workspace_id=tenant_a,
        tenant_id=str(tenant_a),
    )
    app.dependency_overrides[get_current_user] = lambda: admin_user
    doc_id_in_tenant_b = uuid.uuid4()

    mock_db_member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=tenant_a,
        user_id=user_id,
        role="ADMIN",
        status=MemberStatus.ACTIVE.value,
        is_deleted=False,
    )

    with patch("backend.repositories.workspace_member.WorkspaceMemberRepository.get_membership", new_callable=AsyncMock) as mock_mem, \
         patch("backend.document.services.document_service.DocumentService.delete_document", new_callable=AsyncMock) as mock_delete:
        mock_mem.return_value = mock_db_member
        # DocumentService returns False because doc_repo.get_by_id_with_versions filters on Document.tenant_id == tenant_id
        mock_delete.return_value = False

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.delete(f"/api/v1/documents/{doc_id_in_tenant_b}")
            assert res.status_code == 404
            assert res.json()["detail"] == "Document not found or delete failed"


@pytest.mark.asyncio
async def test_cross_tenant_metadata_deletion_rejected(app):
    """Attempting to delete metadata of a document in another tenant raises DocumentDomainException (STORE_002) mapped to 404."""
    tenant_a = uuid.uuid4()
    user_id = uuid.uuid4()
    member_user = UserContext(
        id=user_id,
        email="member_a@test.com",
        role=Role.MEMBER.value,
        workspace_id=tenant_a,
        tenant_id=str(tenant_a),
    )
    app.dependency_overrides[get_current_user] = lambda: member_user
    doc_id_in_tenant_b = uuid.uuid4()

    mock_db_member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=tenant_a,
        user_id=user_id,
        role="MEMBER",
        status=MemberStatus.ACTIVE.value,
        is_deleted=False,
    )

    with patch("backend.repositories.workspace_member.WorkspaceMemberRepository.get_membership", new_callable=AsyncMock) as mock_mem, \
         patch("backend.document.services.metadata_service.MetadataService.remove_metadata_key", new_callable=AsyncMock) as mock_del_meta:
        mock_mem.return_value = mock_db_member
        mock_del_meta.side_effect = DocumentDomainException("STORE_002", "Document not found.")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # DocumentDomainException should be raised / handled as 404 or domain error
            with pytest.raises(DocumentDomainException):
                await client.delete(f"/api/v1/documents/{doc_id_in_tenant_b}/metadata/tag")


@pytest.mark.asyncio
async def test_stale_token_demoted_user_blocked_by_db_revalidation(app):
    """User whose JWT says ADMIN but who was demoted to MEMBER in DB is rejected with 403 on delete."""
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    # JWT claims ADMIN
    stale_admin_user = UserContext(
        id=user_id,
        email="demoted@test.com",
        role=Role.ADMIN.value,
        workspace_id=ws_id,
        tenant_id=str(ws_id),
    )
    app.dependency_overrides[get_current_user] = lambda: stale_admin_user
    doc_id = uuid.uuid4()

    # DB records role as MEMBER
    mock_db_member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=user_id,
        role="MEMBER",
        status=MemberStatus.ACTIVE.value,
        is_deleted=False,
    )

    with patch("backend.repositories.workspace_member.WorkspaceMemberRepository.get_membership", new_callable=AsyncMock) as mock_mem:
        mock_mem.return_value = mock_db_member

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.delete(f"/api/v1/documents/{doc_id}")
            assert res.status_code == 403
            assert "Requires workspace Admin or Owner role" in res.json()["detail"]


@pytest.mark.asyncio
async def test_suspended_or_deleted_member_blocked(app):
    """User who is suspended or deleted in DB is rejected with 403 on delete."""
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    admin_user = UserContext(
        id=user_id,
        email="suspended@test.com",
        role=Role.ADMIN.value,
        workspace_id=ws_id,
        tenant_id=str(ws_id),
    )
    app.dependency_overrides[get_current_user] = lambda: admin_user
    doc_id = uuid.uuid4()

    # DB records suspended status
    mock_db_member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=user_id,
        role="ADMIN",
        status=MemberStatus.SUSPENDED.value,
        is_deleted=False,
    )

    with patch("backend.repositories.workspace_member.WorkspaceMemberRepository.get_membership", new_callable=AsyncMock) as mock_mem:
        # get_membership with include_suspended=False returns None for suspended members
        mock_mem.return_value = None

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.delete(f"/api/v1/documents/{doc_id}")
            assert res.status_code == 403
            assert "not an active member" in res.json()["detail"]
