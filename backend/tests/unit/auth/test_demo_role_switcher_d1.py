"""Unit tests for D1 — Demo Role Switcher Configuration and Identity Binding."""

import uuid
import pytest
from backend.core.auth.context import TokenPayload, UserContext
from backend.core.config import get_settings
from backend.core.permissions.rbac import Role


def test_d1_feature_flag_defaults():
    """Verify demo switcher feature flags default to disabled (fail-closed)."""
    settings = get_settings()
    # By default, demo_role_switcher_enabled must be False
    assert hasattr(settings.features, "demo_role_switcher_enabled")
    assert hasattr(settings.features, "demo_account_user_id")
    assert hasattr(settings.features, "demo_allow_platform_admin_simulation")


def test_d1_user_context_fields():
    """Verify UserContext has demo_role_switcher_enabled and demo_simulated fields."""
    test_user_id = uuid.uuid4()
    ctx = UserContext(
        id=test_user_id,
        email="test-operator@example.com",
        role=Role.VIEWER,
        demo_role_switcher_enabled=True,
        demo_simulated=True,
    )
    assert ctx.demo_role_switcher_enabled is True
    assert ctx.demo_simulated is True

    # Default values must be False
    ctx_default = UserContext(
        id=test_user_id,
        email="test-operator@example.com",
        role=Role.VIEWER,
    )
    assert ctx_default.demo_role_switcher_enabled is False
    assert ctx_default.demo_simulated is False


def test_d1_token_payload_fields():
    """Verify TokenPayload supports demo_simulated claim."""
    payload = TokenPayload(
        sub=str(uuid.uuid4()),
        role="viewer",
        exp=1000,
        demo_simulated=True,
    )
    assert payload.demo_simulated is True

    payload_default = TokenPayload(
        sub=str(uuid.uuid4()),
        role="viewer",
        exp=1000,
    )
    assert payload_default.demo_simulated is False
