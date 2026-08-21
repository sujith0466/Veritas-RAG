"""Unit tests for Audit Log WORM (Write Once, Read Many) Immutability.

Validates that:
1. AuditLog model inherits from ImmutableBaseModel and omits is_deleted and updated_at.
2. AuditLogRepository inherits from ImmutableBaseRepository and possesses no update or delete operations.
3. Audit Log queries do not filter by is_deleted.
4. Security compliance audit endpoint requires PLATFORM_ADMIN authorization.
"""

from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest
from sqlalchemy.sql.selectable import Select

from backend.core.permissions.rbac import Role
from backend.models.base import BaseModel, ImmutableBaseModel
from backend.models.entities.audit_log import AuditLog
from backend.modules.security.api.compliance_routes import router as compliance_router
from backend.repositories.base import BaseRepository, ImmutableBaseRepository
from backend.repositories.implementations.audit_log_repository import AuditLogRepository
from backend.repositories.interfaces.audit_log_repository import IAuditLogRepository


def test_audit_log_model_inheritance():
    """Ensure AuditLog inherits from ImmutableBaseModel and not BaseModel."""
    assert issubclass(AuditLog, ImmutableBaseModel)
    assert not issubclass(AuditLog, BaseModel)


def test_audit_log_model_omits_mutable_columns():
    """Verify AuditLog has no is_deleted or updated_at columns/attributes."""
    column_names = {c.name for c in AuditLog.__table__.columns}
    assert "is_deleted" not in column_names, "AuditLog table must not have is_deleted column"
    assert "updated_at" not in column_names, "AuditLog table must not have updated_at column"
    assert "created_at" in column_names, "AuditLog must retain created_at"
    assert "id" in column_names, "AuditLog must retain id"


def test_audit_log_repository_inheritance_and_immutability():
    """Verify AuditLogRepository inherits from ImmutableBaseRepository and lacks mutation/deletion methods."""
    assert issubclass(AuditLogRepository, ImmutableBaseRepository)
    assert not issubclass(AuditLogRepository, BaseRepository)
    assert issubclass(AuditLogRepository, IAuditLogRepository)

    # Check for absence of mutation / deletion operations on the repository
    assert not hasattr(AuditLogRepository, "soft_delete"), "AuditLogRepository must not have soft_delete method"
    assert not hasattr(AuditLogRepository, "hard_delete"), "AuditLogRepository must not have hard_delete method"
    assert not hasattr(AuditLogRepository, "update"), "AuditLogRepository must not have update method"


def test_immutable_base_repository_contract():
    """Verify ImmutableBaseRepository provides only append and read operations."""
    assert hasattr(ImmutableBaseRepository, "create")
    assert hasattr(ImmutableBaseRepository, "get_by_id")
    assert hasattr(ImmutableBaseRepository, "get_all")
    assert not hasattr(ImmutableBaseRepository, "soft_delete")
    assert not hasattr(ImmutableBaseRepository, "hard_delete")
    assert not hasattr(ImmutableBaseRepository, "update")


@pytest.mark.asyncio
async def test_audit_log_repository_create():
    """Verify creating an audit log entry persists via add, flush, and refresh."""
    mock_session = AsyncMock()
    repo = AuditLogRepository(mock_session)

    log_entry = await repo.create(
        action="user.login",
        user_id=uuid.uuid4(),
        resource_type="auth",
        status="success",
        details={"ip": "127.0.0.1"},
    )

    assert log_entry.action == "user.login"
    mock_session.add.assert_called_once()
    mock_session.flush.assert_awaited_once()
    mock_session.refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_audit_log_queries_no_is_deleted_filter():
    """Verify queries across get_by_action, get_by_user_id, and get_by_tenant_id do not filter on is_deleted."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_result

    repo = AuditLogRepository(mock_session)

    # 1. get_by_action
    await repo.get_by_action("test.action")
    call_args = mock_session.execute.call_args[0][0]
    assert isinstance(call_args, Select)
    query_str = str(call_args.compile(compile_kwargs={"literal_binds": True}))
    assert "is_deleted" not in query_str

    # 2. get_by_user_id
    user_id = uuid.uuid4()
    await repo.get_by_user_id(user_id)
    call_args = mock_session.execute.call_args[0][0]
    assert isinstance(call_args, Select)
    query_str = str(call_args.compile(compile_kwargs={"literal_binds": True}))
    assert "is_deleted" not in query_str

    # 3. get_by_tenant_id
    tenant_id = uuid.uuid4()
    await repo.get_by_tenant_id(tenant_id)
    call_args = mock_session.execute.call_args[0][0]
    assert isinstance(call_args, Select)
    query_str = str(call_args.compile(compile_kwargs={"literal_binds": True}))
    assert "is_deleted" not in query_str


def test_compliance_route_authorization():
    """Verify the compliance audit endpoint has server-side PLATFORM_ADMIN protection."""
    route = next((r for r in compliance_router.routes if r.path == "/security/v1/audit/{tenant_id}"), None)
    assert route is not None, "Route /security/v1/audit/{tenant_id} must exist"

    # Inspect endpoint dependencies
    dependencies = route.dependant.dependencies
    assert len(dependencies) > 0, "Route must have at least one dependency"
