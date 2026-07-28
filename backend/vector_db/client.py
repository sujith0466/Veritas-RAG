"""Qdrant Vector Database Async Client and Health Checks.

Provides singleton management for `AsyncQdrantClient`, dependency injection
helpers, and health monitoring.
"""

from collections.abc import AsyncGenerator
from typing import Any

import structlog
from qdrant_client import AsyncQdrantClient

from backend.core.config import get_settings

logger = structlog.get_logger(__name__)


import asyncio
import weakref

class _VectorDbState:
    clients: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
    fallback_client: AsyncQdrantClient | None = None

_state = _VectorDbState()

def get_qdrant_client() -> AsyncQdrantClient:
    """Return the AsyncQdrantClient instance for the current event loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None:
        if loop in _state.clients:
            return _state.clients[loop]
    else:
        if _state.fallback_client is not None:
            return _state.fallback_client

    settings = get_settings().qdrant
    client_kwargs: dict[str, Any] = {
        "prefer_grpc": settings.prefer_grpc,
    }

    if settings.url_override:
        client_kwargs["url"] = settings.url_override
    else:
        client_kwargs["host"] = settings.host
        client_kwargs["port"] = settings.port
        
    if settings.api_key:
        client_kwargs["api_key"] = settings.api_key

    logger.info(
        "Initializing AsyncQdrantClient", host=settings.host, port=settings.port, loop_id=id(loop) if loop else 0
    )
    client = AsyncQdrantClient(**client_kwargs)
    
    if loop is not None:
        _state.clients[loop] = client
    else:
        _state.fallback_client = client
        
    return client


async def get_vector_db() -> AsyncGenerator[AsyncQdrantClient, None]:
    """FastAPI dependency yielding the AsyncQdrantClient instance."""
    yield get_qdrant_client()


async def check_vector_db_health() -> bool:
    """Check Qdrant connectivity by retrieving the collections list."""
    try:
        client = get_qdrant_client()
        await client.get_collections()
        return True
    except Exception as exc:
        logger.warning("Qdrant vector database health check failed", error=str(exc))
        return False


async def close_vector_db() -> None:
    """Close the Qdrant async client cleanly during application shutdown."""
    for loop, client in list(_state.clients.items()):
        logger.info("Closing AsyncQdrantClient", loop_id=id(loop))
        await client.close()
    _state.clients.clear()
    
    if _state.fallback_client:
        await _state.fallback_client.close()
        _state.fallback_client = None
