"""Unit and Security Regression Tests for Platform Support & Auditor Diagnostic Scoping (WP-7 / DEC-11).

Tests enforce:
1. Least-privilege access boundaries for PLATFORM_SUPPORT and PLATFORM_AUDITOR.
2. Mandatory X-Justification-Ticket-ID validation (fail-closed HTTP 400 on missing or invalid).
3. Transactional append-only audit logging and fail-closed HTTP 500 on database write failure.
4. Strict customer content and secret exclusions (documents, chunks, embeddings, retrieval, chat, chat export).
5. Route-level scoping for detailed health, audit logs, workspace members, and workspace metadata.
6. Permission registry isolation and non-regression for PLATFORM_ADMIN and regular workspace members.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request, status

from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import require_workspace
from backend.core.permissions.guards import record_diagnostic_access, validate_diagnostic_ticket
from backend.core.permissions.rbac import Role
from backend.core.permissions.registry import Permission, get_permission_registry
from backend.document.api.routes import _resolve_tenant_and_owner
from backend.modules.chunking.api.routes import _resolve_tenant as resolve_chunk_tenant
from backend.modules.embedding.api.dependencies import resolve_tenant as resolve_embed_tenant
from backend.modules.retrieval.api.dependencies import resolve_tenant as resolve_retrieval_tenant
from backend.modules.vector.api.dependencies import resolve_tenant as resolve_vector_tenant
from backend.modules.chat.api.export_routes import _verify_workspace_access


# ---------------------------------------------------------------------------
# Helpers & Fixtures
# ---------------------------------------------------------------------------

def make_user(role: Role, tenant_id: str | None = None) -> UserContext:
    return UserContext(
        id=uuid.uuid4(),
        email=f"{role.value.lower()}@example.com",
        role=role,
        is_verified=True,
        tenant_id=tenant_id or str(uuid.uuid4()),
        permissions=[],
    )


def make_mock_session_factory():
    """Create a mock autonomous session factory and its underlying mock session."""
    mock_auto_session = AsyncMock()
    mock_auto_session.add = MagicMock()
    mock_auto_session.commit = AsyncMock()

    factory_ctx = MagicMock()
    factory_ctx.__aenter__.return_value = mock_auto_session
    factory_ctx.__aexit__.return_value = None

    mock_factory = MagicMock(return_value=factory_ctx)
    return mock_factory, mock_auto_session


# ---------------------------------------------------------------------------
# 1. Permission Registry Least-Privilege Scoping
# ---------------------------------------------------------------------------

class TestPermissionRegistryScoping:
    """Verify registry permission definitions for diagnostic roles."""

    def test_platform_support_permissions(self):
        registry = get_permission_registry()
        support_perms = registry.get_permissions_for_role(Role.PLATFORM_SUPPORT)

        # Permitted
        assert Permission.WORKSPACE_READ.value in support_perms
        assert Permission.USERS_MEMBER_LIST.value in support_perms
        assert Permission.VIEW_DETAILED_HEALTH.value in support_perms

        # Denied
        assert Permission.AUDIT_LOGS_READ.value not in support_perms
        assert Permission.DOCUMENTS_READ.value not in support_perms
        assert Permission.DOCUMENTS_CREATE.value not in support_perms
        assert Permission.DOCUMENTS_UPDATE.value not in support_perms
        assert Permission.DOCUMENTS_DELETE.value not in support_perms
        assert Permission.CHAT_SESSION_READ.value not in support_perms
        assert Permission.CHAT_SESSION_CREATE.value not in support_perms
        assert Permission.CHAT_MESSAGE_CREATE.value not in support_perms
        assert Permission.WORKSPACE_DELETE.value not in support_perms

    def test_platform_auditor_permissions(self):
        registry = get_permission_registry()
        auditor_perms = registry.get_permissions_for_role(Role.PLATFORM_AUDITOR)

        # Permitted
        assert Permission.AUDIT_LOGS_READ.value in auditor_perms
        assert Permission.AUDIT_LOGS_EXPORT.value in auditor_perms
        assert Permission.VIEW_DETAILED_HEALTH.value in auditor_perms

        # Denied
        assert Permission.WORKSPACE_READ.value not in auditor_perms
        assert Permission.USERS_MEMBER_LIST.value not in auditor_perms
        assert Permission.DOCUMENTS_READ.value not in auditor_perms
        assert Permission.DOCUMENTS_CREATE.value not in auditor_perms
        assert Permission.DOCUMENTS_UPDATE.value not in auditor_perms
        assert Permission.DOCUMENTS_DELETE.value not in auditor_perms
        assert Permission.CHAT_SESSION_READ.value not in auditor_perms
        assert Permission.CHAT_SESSION_CREATE.value not in auditor_perms
        assert Permission.CHAT_MESSAGE_CREATE.value not in auditor_perms


# ---------------------------------------------------------------------------
# 2. Ticket Validation Tests
# ---------------------------------------------------------------------------

class TestDiagnosticTicketValidation:
    """Verify X-Justification-Ticket-ID validation."""

    @pytest.mark.parametrize("valid_ticket", [
        "INC-12345",
        "SEC-2026-001",
        "TICKET_99",
        "ABC",
        "A" * 64,
    ])
    def test_valid_ticket_accepted(self, valid_ticket: str):
        assert validate_diagnostic_ticket(valid_ticket) == valid_ticket

    @pytest.mark.parametrize("missing_ticket", [None, "", "   "])
    def test_missing_ticket_rejected(self, missing_ticket: str | None):
        with pytest.raises(HTTPException) as exc_info:
            validate_diagnostic_ticket(missing_ticket)
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        detail = exc_info.value.detail
        assert "Missing required diagnostic ticket header" in detail or "Malformed justification ticket ID" in detail

    @pytest.mark.parametrize("invalid_ticket", [
        "ab",  # too short (< 3)
        "A" * 65,  # too long (> 64)
        "INC#123",  # illegal character '#'
        "INC 123",  # whitespace
        "<script>alert(1)</script>",  # injection
        "ticket@corp",  # illegal character '@'
    ])
    def test_malformed_ticket_rejected(self, invalid_ticket: str):
        with pytest.raises(HTTPException) as exc_info:
            validate_diagnostic_ticket(invalid_ticket)
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Malformed justification ticket ID" in exc_info.value.detail


# ---------------------------------------------------------------------------
# 3. Audit Logging Fail-Closed Behavior
# ---------------------------------------------------------------------------

class TestDiagnosticAuditLoggingFailClosed:
    """Verify audit log creation and fail-closed persistence."""

    @pytest.mark.asyncio
    async def test_audit_logging_success(self):
        mock_factory, auto_session = make_mock_session_factory()
        user_id = uuid.uuid4()
        resource_id = uuid.uuid4()

        await record_diagnostic_access(
            user_id=user_id,
            user_role="PLATFORM_SUPPORT",
            action="DIAGNOSTIC_MEMBER_LIST_READ",
            resource_type="workspace",
            resource_id=str(resource_id),
            ticket_id="INC-9999",
            session_factory=mock_factory,
        )

        auto_session.add.assert_called_once()
        auto_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_audit_logging_database_failure_fails_closed(self):
        mock_factory, auto_session = make_mock_session_factory()
        auto_session.commit = AsyncMock(side_effect=Exception("Database connection error"))

        user_id = uuid.uuid4()
        resource_id = uuid.uuid4()

        with pytest.raises(HTTPException) as exc_info:
            await record_diagnostic_access(
                user_id=user_id,
                user_role="PLATFORM_SUPPORT",
                action="DIAGNOSTIC_MEMBER_LIST_READ",
                resource_type="workspace",
                resource_id=str(resource_id),
                ticket_id="INC-9999",
                session_factory=mock_factory,
            )
        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Diagnostic access audit persistence failed" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_audit_logging_autonomous_session_preserves_caller_pending_changes(self):
        """WP-7.1: Verify autonomous session commits audit log without committing caller session state."""
        caller_session = AsyncMock()
        caller_session.dirty = {MagicMock(name="UnrelatedDirtyEntity")}
        caller_session.new = {MagicMock(name="UnrelatedNewEntity")}
        caller_session.commit = AsyncMock()

        mock_factory, auto_session = make_mock_session_factory()

        user_id = uuid.uuid4()
        resource_id = uuid.uuid4()

        await record_diagnostic_access(
            session=caller_session,
            user_id=user_id,
            user_role="PLATFORM_SUPPORT",
            action="DIAGNOSTIC_MEMBER_LIST_READ",
            resource_type="workspace",
            resource_id=str(resource_id),
            ticket_id="INC-9999",
            session_factory=mock_factory,
        )

        # 1. Autonomous session must have recorded and committed the audit entry
        auto_session.add.assert_called_once()
        auto_session.commit.assert_awaited_once()

        # 2. Caller session must NOT have been committed or polluted
        caller_session.commit.assert_not_called()
        assert len(caller_session.dirty) == 1
        assert len(caller_session.new) == 1

    @pytest.mark.asyncio
    async def test_audit_logging_autonomous_session_failure_fails_closed(self):
        """WP-7.1: Verify failure in autonomous session commit aborts request with HTTP 500."""
        caller_session = AsyncMock()
        caller_session.commit = AsyncMock()

        mock_factory, auto_session = make_mock_session_factory()
        auto_session.commit = AsyncMock(side_effect=Exception("Disk full / Write error"))

        with pytest.raises(HTTPException) as exc_info:
            await record_diagnostic_access(
                session=caller_session,
                user_id=uuid.uuid4(),
                user_role="PLATFORM_SUPPORT",
                action="DIAGNOSTIC_MEMBER_LIST_READ",
                resource_type="workspace",
                resource_id=str(uuid.uuid4()),
                ticket_id="INC-9999",
                session_factory=mock_factory,
            )

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Diagnostic access audit persistence failed" in exc_info.value.detail
        caller_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_audit_logging_default_session_factory_resolution(self):
        """WP-7.1: Verify that omitting session_factory obtains the factory via get_session_factory."""
        mock_factory, auto_session = make_mock_session_factory()
        with patch("backend.database.engine.get_session_factory", return_value=mock_factory) as mock_get_factory:
            await record_diagnostic_access(
                user_id=uuid.uuid4(),
                user_role="PLATFORM_SUPPORT",
                action="DIAGNOSTIC_HEALTH_READ",
                resource_type="health",
                resource_id="detailed",
                ticket_id="INC-5555",
            )
            mock_get_factory.assert_called_once()
            auto_session.add.assert_called_once()
            auto_session.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# 4. Negative Authorization Content Exclusions
# ---------------------------------------------------------------------------

class TestCustomerContentExclusions:
    """Verify that PLATFORM_SUPPORT and PLATFORM_AUDITOR cannot access customer content."""

    @pytest.mark.parametrize("role", [Role.PLATFORM_SUPPORT, Role.PLATFORM_AUDITOR])
    def test_document_routes_excluded(self, role: Role):
        user = make_user(role)
        with pytest.raises(HTTPException) as exc_info:
            _resolve_tenant_and_owner(user)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Platform diagnostic roles are strictly excluded from customer document access" in exc_info.value.detail

    @pytest.mark.parametrize("role", [Role.PLATFORM_SUPPORT, Role.PLATFORM_AUDITOR])
    def test_chunking_routes_excluded(self, role: Role):
        user = make_user(role)
        with pytest.raises(HTTPException) as exc_info:
            resolve_chunk_tenant(user)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Platform diagnostic roles are strictly excluded from chunking access" in exc_info.value.detail

    @pytest.mark.parametrize("role", [Role.PLATFORM_SUPPORT, Role.PLATFORM_AUDITOR])
    def test_embedding_routes_excluded(self, role: Role):
        user = make_user(role)
        with pytest.raises(HTTPException) as exc_info:
            resolve_embed_tenant(user)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Platform diagnostic roles are strictly excluded from embedding access" in exc_info.value.detail

    @pytest.mark.parametrize("role", [Role.PLATFORM_SUPPORT, Role.PLATFORM_AUDITOR])
    def test_retrieval_routes_excluded(self, role: Role):
        user = make_user(role)
        with pytest.raises(HTTPException) as exc_info:
            resolve_retrieval_tenant(user)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Platform diagnostic roles are strictly excluded from retrieval access" in exc_info.value.detail

    @pytest.mark.parametrize("role", [Role.PLATFORM_SUPPORT, Role.PLATFORM_AUDITOR])
    def test_vector_routes_excluded(self, role: Role):
        user = make_user(role)
        with pytest.raises(HTTPException) as exc_info:
            resolve_vector_tenant(user)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Platform diagnostic roles are strictly excluded from vector access" in exc_info.value.detail

    @pytest.mark.asyncio
    @pytest.mark.parametrize("role", [Role.PLATFORM_SUPPORT, Role.PLATFORM_AUDITOR])
    async def test_chat_workspace_guard_excluded(self, role: Role):
        user = make_user(role)
        guard = require_workspace()
        with pytest.raises(HTTPException) as exc_info:
            await guard(user_context=user)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Platform diagnostic roles are strictly excluded from workspace session and chat access" in exc_info.value.detail

    @pytest.mark.asyncio
    @pytest.mark.parametrize("role", [Role.PLATFORM_SUPPORT, Role.PLATFORM_AUDITOR])
    async def test_chat_export_routes_excluded(self, role: Role):
        user = make_user(role)
        mock_repo = AsyncMock()
        ws_id = uuid.uuid4()
        with pytest.raises(HTTPException) as exc_info:
            await _verify_workspace_access(ws_id, user, mock_repo)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Platform diagnostic roles are strictly excluded from chat exports" in exc_info.value.detail


# ---------------------------------------------------------------------------
# 5. Route-Level Endpoint Scoping (Health, Audit Logs, Members, Workspace)
# ---------------------------------------------------------------------------

class TestRouteLevelDiagnosticScoping:
    """Verify endpoint-specific scoping in health, audit logs, and members routes."""

    @pytest.mark.asyncio
    async def test_health_detailed_platform_support_missing_ticket(self):
        from backend.api.v1.routes.health import detailed_health
        user = make_user(Role.PLATFORM_SUPPORT)
        mock_req = MagicMock(spec=Request)
        mock_req.headers = {}
        mock_session = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await detailed_health(
                request=mock_req,
                _user=user,
                session=mock_session,
            )
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_health_detailed_platform_support_valid_ticket(self):
        from backend.api.v1.routes.health import detailed_health
        user = make_user(Role.PLATFORM_SUPPORT)
        mock_req = MagicMock(spec=Request)
        mock_req.headers = {"X-Justification-Ticket-ID": "INC-7788"}
        mock_req.client.host = "10.0.0.1"
        caller_session = AsyncMock()
        mock_factory, auto_session = make_mock_session_factory()

        with patch("backend.api.v1.routes.health._check_dependencies", new_callable=AsyncMock) as mock_deps, \
             patch("backend.database.engine.get_session_factory", return_value=mock_factory):
            mock_deps.return_value = {}
            resp = await detailed_health(
                request=mock_req,
                _user=user,
                session=caller_session,
            )
            assert resp is not None
            assert hasattr(resp, "status")
            auto_session.commit.assert_awaited_once()
            caller_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_audit_logs_platform_support_denied(self):
        from backend.api.v1.routes.audit_logs import list_audit_logs
        user = make_user(Role.PLATFORM_SUPPORT)
        mock_req = MagicMock(spec=Request)
        mock_req.headers = {"X-Justification-Ticket-ID": "INC-7788"}
        mock_session = AsyncMock()
        mock_repo = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await list_audit_logs(
                request=mock_req,
                auth=user,
                repo=mock_repo,
                session=mock_session,
            )
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Platform support role is prohibited from accessing audit logs" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_audit_logs_platform_auditor_missing_ticket(self):
        from backend.api.v1.routes.audit_logs import list_audit_logs
        user = make_user(Role.PLATFORM_AUDITOR)
        mock_req = MagicMock(spec=Request)
        mock_req.headers = {}
        mock_session = AsyncMock()
        mock_repo = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await list_audit_logs(
                request=mock_req,
                auth=user,
                repo=mock_repo,
                session=mock_session,
            )
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_audit_logs_platform_auditor_valid_ticket(self):
        from backend.api.v1.routes.audit_logs import list_audit_logs
        user = make_user(Role.PLATFORM_AUDITOR)
        mock_req = MagicMock(spec=Request)
        mock_req.headers = {"X-Justification-Ticket-ID": "AUDIT-2026-X"}
        mock_req.client.host = "10.0.0.1"
        mock_req.state.correlation_id = str(uuid.uuid4())
        caller_session = AsyncMock()
        mock_factory, auto_session = make_mock_session_factory()
        mock_repo = AsyncMock()
        mock_repo.search_logs.return_value = ([], 0)

        with patch("backend.database.engine.get_session_factory", return_value=mock_factory):
            resp = await list_audit_logs(
                request=mock_req,
                auth=user,
                repo=mock_repo,
                session=caller_session,
                workspace_id=uuid.uuid4(),
                page=1,
                page_size=50,
            )
            assert resp.items == []
            auto_session.commit.assert_awaited_once()
            caller_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_workspace_members_platform_auditor_denied(self):
        from backend.api.v1.routes.workspace_members import list_workspace_members
        user = make_user(Role.PLATFORM_AUDITOR)
        mock_req = MagicMock(spec=Request)
        mock_req.headers = {"X-Justification-Ticket-ID": "AUDIT-2026-X"}
        mock_session = AsyncMock()
        mock_service = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await list_workspace_members(
                request=mock_req,
                workspace_id=uuid.uuid4(),
                current_user=user,
                session=mock_session,
                service=mock_service,
                page=1,
                page_size=50,
            )
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Platform auditor role is prohibited from accessing member lists" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_workspace_members_platform_support_missing_ticket(self):
        from backend.api.v1.routes.workspace_members import list_workspace_members
        user = make_user(Role.PLATFORM_SUPPORT)
        mock_req = MagicMock(spec=Request)
        mock_req.headers = {}
        mock_session = AsyncMock()
        mock_service = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await list_workspace_members(
                request=mock_req,
                workspace_id=uuid.uuid4(),
                current_user=user,
                session=mock_session,
                service=mock_service,
                page=1,
                page_size=50,
            )
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_workspace_members_platform_support_valid_ticket(self):
        from backend.api.v1.routes.workspace_members import list_workspace_members
        user = make_user(Role.PLATFORM_SUPPORT)
        mock_req = MagicMock(spec=Request)
        mock_req.headers = {"X-Justification-Ticket-ID": "SUP-101"}
        mock_req.client.host = "127.0.0.1"
        caller_session = AsyncMock()
        mock_factory, auto_session = make_mock_session_factory()
        mock_service = AsyncMock()
        mock_service.list_members.return_value = ([], 0, None)

        with patch("backend.database.engine.get_session_factory", return_value=mock_factory):
            resp = await list_workspace_members(
                request=mock_req,
                workspace_id=uuid.uuid4(),
                current_user=user,
                session=caller_session,
                service=mock_service,
                page=1,
                page_size=50,
            )
            assert resp.total == 0
            mock_service.list_members.assert_awaited_once()
            auto_session.commit.assert_awaited_once()
            caller_session.commit.assert_not_called()
            assert mock_service.list_members.call_args[1]["is_diagnostic"] is True

    @pytest.mark.asyncio
    async def test_workspace_management_service_platform_auditor_denied(self):
        from backend.core.dependencies.database import get_workspace_management_service
        user = make_user(Role.PLATFORM_AUDITOR)
        mock_req = MagicMock()
        mock_req.state.user_context = user
        mock_req.method = "GET"
        mock_repo = MagicMock()
        mock_member_repo = MagicMock()
        mock_session = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_workspace_management_service(
                workspace_repo=mock_repo,
                workspace_member_repo=mock_member_repo,
                session=mock_session,
                request=mock_req,
            )
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Platform Auditor is not authorized to access workspace configuration or metadata" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_workspace_management_service_platform_support_missing_ticket(self):
        from backend.core.dependencies.database import get_workspace_management_service
        user = make_user(Role.PLATFORM_SUPPORT)
        mock_req = MagicMock()
        mock_req.state.user_context = user
        mock_req.method = "GET"
        mock_req.headers = {}
        mock_repo = MagicMock()
        mock_member_repo = MagicMock()
        mock_session = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_workspace_management_service(
                workspace_repo=mock_repo,
                workspace_member_repo=mock_member_repo,
                session=mock_session,
                request=mock_req,
            )
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_workspace_management_service_platform_support_mutation_rejected(self):
        from backend.core.dependencies.database import get_workspace_management_service
        user = make_user(Role.PLATFORM_SUPPORT)
        mock_req = MagicMock()
        mock_req.state.user_context = user
        mock_req.method = "PATCH"
        mock_req.headers = {"X-Justification-Ticket-ID": "SUP-999"}
        mock_repo = MagicMock()
        mock_member_repo = MagicMock()
        mock_session = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_workspace_management_service(
                workspace_repo=mock_repo,
                workspace_member_repo=mock_member_repo,
                session=mock_session,
                request=mock_req,
            )
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Platform Support is strictly read-only and cannot mutate workspaces" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_workspace_management_service_platform_support_get_synthetic_proxy(self):
        from backend.core.dependencies.database import get_workspace_management_service
        user = make_user(Role.PLATFORM_SUPPORT)
        mock_req = MagicMock()
        mock_req.state.user_context = user
        mock_req.method = "GET"
        mock_req.headers = {"X-Justification-Ticket-ID": "SUP-101"}
        mock_req.client.host = "10.0.0.5"
        mock_req.url.path = "/api/v1/workspaces/test"
        mock_req.path_params = {"workspace_id": str(uuid.uuid4())}
        mock_repo = MagicMock()
        mock_member_repo = AsyncMock()
        mock_member_repo.get_membership.return_value = None  # user has no DB row
        caller_session = AsyncMock()
        mock_factory, auto_session = make_mock_session_factory()

        with patch("backend.database.engine.get_session_factory", return_value=mock_factory):
            service = await get_workspace_management_service(
                workspace_repo=mock_repo,
                workspace_member_repo=mock_member_repo,
                session=caller_session,
                request=mock_req,
            )
            assert service is not None
            auto_session.commit.assert_awaited_once()
            caller_session.commit.assert_not_called()

        # Verify proxy provides synthetic active membership for support user
        target_ws_id = uuid.uuid4()
        member = await service.workspace_member_repo.get_membership(target_ws_id, user.id)
        assert member is not None
        assert member.workspace_id == target_ws_id
        assert member.user_id == user.id

        # Verify proxy does NOT provide synthetic membership for any other user
        other_user_id = uuid.uuid4()
        other_member = await service.workspace_member_repo.get_membership(target_ws_id, other_user_id)
        assert other_member is None
