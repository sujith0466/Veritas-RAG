"""Qdrant Vector Database Async Client and Health Checks.

Provides singleton management for `AsyncQdrantClient`, dependency injection
helpers, and health monitoring.
"""

from collections.abc import AsyncGenerator
from typing import Any

from qdrant_client import AsyncQdrantClient
import structlog

from backend.core.config import get_settings

logger = structlog.get_logger(__name__)


class _VectorDbState:
    client: AsyncQdrantClient | None = None


_state = _VectorDbState()


def get_qdrant_client() -> AsyncQdrantClient:
    """Return the singleton AsyncQdrantClient instance, initializing it if needed."""
    if _state.client is not None:
        return _state.client

    settings = get_settings().qdrant
    client_kwargs: dict[str, Any] = {
        "host": settings.host,
        "port": settings.port,
        "grpc_port": settings.grpc_port,
        "prefer_grpc": settings.prefer_grpc,
    }
    if settings.api_key:
        client_kwargs["api_key"] = settings.api_key

    logger.info("Initializing AsyncQdrantClient", host=settings.host, port=settings.port)
    _state.client = AsyncQdrantClient(**client_kwargs)
    return _state.client


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
    if _state.client is not None:
        logger.info("Closing AsyncQdrantClient")
        await _state.client.close()
        _state.client = None
