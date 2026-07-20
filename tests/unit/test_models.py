"""Unit tests for SQLAlchemy entity models and BaseModel behavior."""

import uuid

import pytest

from backend.models import AuditLog, User


@pytest.mark.unit
class TestEntityModels:
    def test_user_model_defaults_and_repr(self) -> None:
        user = User(email="architect@raguard.ai", role="admin", is_active=True)
        assert user.email == "architect@raguard.ai"
        assert user.role == "admin"
        assert user.is_active is True
        assert repr(user) == f"<User(id={user.id}, email='architect@raguard.ai', role='admin')>"

        # Verify ORM column default definitions for INSERT
        role_col = User.__table__.columns["role"]
        active_col = User.__table__.columns["is_active"]
        assert role_col.default.arg == "user"
        assert active_col.default.arg is True

    def test_audit_log_model_defaults_and_repr(self) -> None:
        log_id = uuid.uuid4()
        log = AuditLog(id=log_id, action="LOGIN_ATTEMPT", status="success")
        assert log.action == "LOGIN_ATTEMPT"
        assert log.status == "success"
        assert log.id == log_id
        assert repr(log) == f"<AuditLog(id={log_id}, action='LOGIN_ATTEMPT', status='success')>"

        status_col = AuditLog.__table__.columns["status"]
        assert status_col.default.arg == "success"

    def test_base_model_to_dict(self) -> None:
        user = User(email="test@raguard.ai", role="user")
        user_dict = user.to_dict()
        assert user_dict["email"] == "test@raguard.ai"
        assert user_dict["role"] == "user"
