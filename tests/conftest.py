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

# ── Environment: force testing mode before any imports ────────────────────────
os.environ.setdefault("APP_ENVIRONMENT", "testing")
os.environ.setdefault("APP_DEBUG", "true")
os.environ.setdefault("APP_SECRET_KEY", "test-secret-key-32-characters-ok!")
os.environ.setdefault("APP_NAME", "RAGuard AI Test")
os.environ.setdefault("APP_VERSION", "1.0.0-test")

# Supabase
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret")

# Database (scaffold)
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/raguard_test"
)
os.environ.setdefault(
    "ALEMBIC_DATABASE_URL", "postgresql://test:test@localhost:5432/raguard_test"
)

# Redis (scaffold)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")

# Qdrant (scaffold)
os.environ.setdefault("QDRANT_HOST", "localhost")
os.environ.setdefault("QDRANT_PORT", "6333")

# Gemini
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-api-key")


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
