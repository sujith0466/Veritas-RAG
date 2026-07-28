"""SQLAlchemy 2.x Async Engine and Session Management.

Provides connection pooling, async session factory (`async_sessionmaker`),
and health check capabilities for the PostgreSQL database.
"""

import asyncio
import weakref
from typing import Any
from collections.abc import AsyncGenerator

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (AsyncEngine, AsyncSession,
                                    async_sessionmaker, create_async_engine)

from backend.core.config import get_settings

logger = structlog.get_logger(__name__)

class _EngineState:
    engines: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
    sessionmakers: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
    fallback_engine: AsyncEngine | None = None
    fallback_sessionmaker: async_sessionmaker[AsyncSession] | None = None

_state = _EngineState()

def get_engine() -> AsyncEngine:
    """Return the AsyncEngine instance, isolated per event loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None:
        if loop in _state.engines:
            return _state.engines[loop]
    else:
        if _state.fallback_engine is not None:
            return _state.fallback_engine

    settings = get_settings().database
    url = settings.url

    engine_kwargs: dict[str, Any] = {
        "echo": settings.echo,
        "pool_pre_ping": True,
    }

    import sys
    is_celery = any("celery" in arg for arg in sys.argv)
    
    if is_celery:
        from sqlalchemy.pool import NullPool
        engine_kwargs["poolclass"] = NullPool
    elif "sqlite" not in url:
        engine_kwargs.update(
            {
                "pool_size": settings.pool_size,
                "max_overflow": settings.max_overflow,
                "pool_timeout": settings.pool_timeout,
                "pool_recycle": settings.pool_recycle,
            }
        )

    logger.info("Initializing SQLAlchemy AsyncEngine", url=url.split("@")[-1], loop_id=id(loop) if loop else 0, is_celery=is_celery)
    engine = create_async_engine(url, **engine_kwargs)
    
    if loop is not None:
        _state.engines[loop] = engine
    else:
        _state.fallback_engine = engine
        
    return engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the async_sessionmaker isolated per event loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None:
        if loop in _state.sessionmakers:
            return _state.sessionmakers[loop]
    else:
        if _state.fallback_sessionmaker is not None:
            return _state.fallback_sessionmaker

    engine = get_engine()
    factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    
    if loop is not None:
        _state.sessionmakers[loop] = factory
    else:
        _state.fallback_sessionmaker = factory
        
    return factory


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an isolated AsyncSession per request."""
    session_maker = get_session_factory()
    async with session_maker() as session:
        try:
            yield session
        except Exception as exc:
            try:
                await session.rollback()
            except Exception:
                pass
            logger.error(
                "Database transaction rolled back due to error", error=str(exc)
            )
            raise
        finally:
            try:
                await session.close()
            except Exception:
                pass


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
    """Dispose the database engines cleanly during application shutdown."""
    for loop, engine in list(_state.engines.items()):
        logger.info("Disposing SQLAlchemy AsyncEngine", loop_id=id(loop))
        await engine.dispose()
    _state.engines.clear()
    _state.sessionmakers.clear()
    
    if _state.fallback_engine:
        await _state.fallback_engine.dispose()
        _state.fallback_engine = None
        _state.fallback_sessionmaker = None

