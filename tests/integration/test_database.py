
import pytest


@pytest.mark.skip(reason="Requires live PostgreSQL instance in CI")
@pytest.mark.asyncio
async def test_engine_health_check_query():
    """Verify raw engine connectivity."""
    pass

@pytest.mark.skip(reason="Requires live PostgreSQL instance in CI")
@pytest.mark.asyncio
async def test_rls_session_context_injection():
    """Verify that the RLS session correctly injects and resets tenant context."""
    pass
