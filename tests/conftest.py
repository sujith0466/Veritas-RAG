"""Pytest root configuration and shared fixtures.

This conftest.py is the top-level fixture hub. All fixtures defined here
are available to every test in the suite.

Fixture scope strategy:
- session: expensive setup done once per test session (DB engine, app)
- function: reset state between tests (DB transactions, mock state)
"""

from collections.abc import Generator
import os
from typing import Any

import pytest

# ─── Environment: force testing mode before any imports ────────────────────────
os.environ["APP_ENVIRONMENT"] = "testing"
os.environ["VALIDATE_INFRASTRUCTURE"] = "false"
os.environ["APP_DEBUG"] = "true"
os.environ["APP_SECRET_KEY"] = "test-secret-key-32-characters-ok!"
os.environ["APP_NAME"] = "RAGuard AI Test"
os.environ["APP_VERSION"] = "1.0.0-test"

# Supabase
os.environ["SUPABASE_URL"] = "https://test.supabase.co"
os.environ["SUPABASE_ANON_KEY"] = "test-anon-key"
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "test-service-role-key"
os.environ["SUPABASE_JWT_SECRET"] = "test-jwt-secret"

# Database (scaffold)
os.environ["DATABASE_URL"] = "postgresql+asyncpg://test:test@localhost:5432/raguard_test"
os.environ["ALEMBIC_DATABASE_URL"] = "postgresql://test:test@localhost:5432/raguard_test"

# Redis (scaffold)
os.environ["REDIS_URL"] = "redis://localhost:6379/15"

# Qdrant (scaffold)
os.environ["QDRANT_HOST"] = "localhost"
os.environ["QDRANT_PORT"] = "6333"
# Clear URL to not conflict with Qdrant config
if "QDRANT_URL" in os.environ:
    del os.environ["QDRANT_URL"]

# Gemini
os.environ["GEMINI_API_KEY"] = "test-gemini-api-key"


# ── Settings cache reset ───────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_settings_cache() -> Generator[None, None, None]:
    """Clear the lru_cache on get_settings() before each test.

    This ensures that environment variable changes in tests are picked up
    by a fresh Settings instance.
    """
    from backend.core.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ── FastAPI test client ────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def app() -> Any:
    """Create the FastAPI application for testing."""
    from backend.main import create_app
    return create_app()


@pytest.fixture
def client(app: Any) -> Generator[Any, None, None]:
    """Synchronous test client for the FastAPI application."""
    from fastapi.testclient import TestClient
    # Use raise_server_exceptions=False to test error response shapes
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
