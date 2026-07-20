"""FastAPI database and repository dependency providers.

Yields request-scoped database sessions, Redis/Qdrant clients, and repositories.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import Depends

from backend.cache.client import get_cache as _get_cache
from backend.database.engine import get_async_session
from backend.repositories import (
    AuditLogRepository,
    IAuditLogRepository,
    IUserRepository,
    UserRepository,
)
from backend.vector_db.client import get_vector_db as _get_vector_db

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from qdrant_client import AsyncQdrantClient
    from redis.asyncio import Redis
    from sqlalchemy.ext.asyncio import AsyncSession


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an isolated async database session per request."""
    async for session in get_async_session():
        yield session


async def get_cache() -> AsyncGenerator[Redis[Any], None]:
    """Yield an async Redis client instance per request."""
    async for client in _get_cache():
        yield client


async def get_vector_db() -> AsyncGenerator[AsyncQdrantClient, None]:
    """Yield an async Qdrant client instance per request."""
    async for client in _get_vector_db():
        yield client


async def get_user_repository(
    session: AsyncSession = Depends(get_db),
) -> IUserRepository:
    """FastAPI dependency yielding a UserRepository instance."""
    return UserRepository(session)


async def get_audit_log_repository(
    session: AsyncSession = Depends(get_db),
) -> IAuditLogRepository:
    """FastAPI dependency yielding an AuditLogRepository instance."""
    return AuditLogRepository(session)
