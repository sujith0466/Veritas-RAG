"""SQLAlchemy 2.x Async Engine and Session Management.

Provides connection pooling, async session factory (`async_sessionmaker`),
and health check capabilities for the PostgreSQL database.
"""

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
import structlog

from backend.core.config import get_settings

logger = structlog.get_logger(__name__)


class _EngineState:
    engine: AsyncEngine | None = None
    sessionmaker: async_sessionmaker[AsyncSession] | None = None


_state = _EngineState()


def get_engine() -> AsyncEngine:
    """Return the singleton AsyncEngine instance, creating it if needed."""
    if _state.engine is not None:
        return _state.engine

    settings = get_settings().database
    url = settings.url

    engine_kwargs: dict[str, Any] = {
        "echo": settings.echo,
        "pool_pre_ping": True,
    }

    # Only pass pool arguments if using PostgreSQL / asyncpg (not SQLite)
    if "sqlite" not in url:
        engine_kwargs.update({
            "pool_size": settings.pool_size,
            "max_overflow": settings.max_overflow,
            "pool_timeout": settings.pool_timeout,
            "pool_recycle": settings.pool_recycle,
        })

    logger.info("Initializing SQLAlchemy AsyncEngine", url=url.split("@")[-1])
    _state.engine = create_async_engine(url, **engine_kwargs)
    return _state.engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the singleton async_sessionmaker instance."""
    if _state.sessionmaker is not None:
        return _state.sessionmaker

    engine = get_engine()
    _state.sessionmaker = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    return _state.sessionmaker


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an isolated AsyncSession per request."""
    session_maker = get_session_factory()
    async with session_maker() as session:
        try:
            yield session
        except Exception as exc:
            await session.rollback()
            logger.error("Database transaction rolled back due to error", error=str(exc))
            raise
        finally:
            await session.close()


async def check_db_health() -> bool:
    """Check database connectivity by executing SELECT 1."""
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.warning("Database health check failed", error=str(exc))
        return False


async def close_db() -> None:
    """Dispose the database engine cleanly during application shutdown."""
    if _state.engine is not None:
        logger.info("Disposing SQLAlchemy AsyncEngine")
        await _state.engine.dispose()
        _state.engine = None
        _state.sessionmaker = None
