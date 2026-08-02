"""Database Session Managers.

Provides context managers for isolated RLS database access.
"""

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.engine import get_session_factory


@asynccontextmanager
async def rls_session(tenant_id: str | uuid.UUID) -> AsyncGenerator[AsyncSession, None]:
    """Context manager for yielding a session with Row-Level Security applied.

    Executes `SET LOCAL app.current_tenant_id` before yielding.
    Since `SET LOCAL` is transaction-scoped, it automatically resets on commit/rollback.
    """
    factory = get_session_factory()
    
    tenant_str = str(tenant_id)
    
    async with factory() as session:
        try:
            # Enforce RLS context at the transaction level
            await session.execute(text(f"SET LOCAL app.current_tenant_id = '{tenant_str}'"))
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
