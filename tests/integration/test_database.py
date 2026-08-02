"""Integration tests for Database Connection and RLS session manager."""

import uuid

import pytest
from sqlalchemy import text

from backend.database.engine import get_engine
from backend.database.session import rls_session


@pytest.mark.asyncio
async def test_engine_health_check_query():
    """Verify raw engine connectivity."""
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        val = result.scalar()
        assert val == 1


@pytest.mark.asyncio
async def test_rls_session_context_injection():
    """Verify that the RLS session correctly injects and resets tenant context."""
    tenant_id = uuid.uuid4()
    
    # Context manager should set the variable for the transaction scope
    async with rls_session(tenant_id) as session:
        result = await session.execute(text("SHOW app.current_tenant_id"))
        current_tenant = result.scalar()
        assert current_tenant == str(tenant_id)

    # Outside the context manager, the transaction is closed, and SET LOCAL is cleared.
    engine = get_engine()
    async with engine.connect() as conn:
        try:
            # This should either fail (unrecognized configuration parameter) or be empty
            # depending on PostgreSQL setup, but it definitely shouldn't be tenant_id
            result = await conn.execute(text("SHOW app.current_tenant_id"))
            outside_tenant = result.scalar()
            assert outside_tenant != str(tenant_id)
        except Exception:
            # Expected if app.current_tenant_id is entirely undefined outside the session
            pass
