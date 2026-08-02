"""Qdrant Vector Database Async Client and Health Checks.

Provides singleton management for `AsyncQdrantClient`, dependency injection
helpers, and health monitoring.
"""

from collections.abc import AsyncGenerator
from typing import Any

import structlog
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse
import httpx

from backend.core.config import get_settings
from backend.core.utils.retry import with_retry
from backend.vector_db.metrics import QdrantMetrics
import time

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


async def check_vector_db_health() -> dict[str, Any]:
    """Check Qdrant connectivity and measure latency.
    
    Returns detailed connection status, latency in ms, and gRPC preference.
    """
    start = time.perf_counter()
    status = "healthy"
    error = None
    collection_count = 0
    grpc_enabled = False
    
    try:
        # Wrap the ping with the generic retry utility for transient network errors
        @with_retry(
            max_retries=get_settings().qdrant.retry_attempts,
            base_delay=0.5,
            exceptions=(ResponseHandlingException, UnexpectedResponse, httpx.ConnectError)
        )
        async def _ping():
            client = get_qdrant_client()
            res = await client.get_collections()
            return client, res
            
        client, res = await _ping()
        collection_count = len(res.collections) if res and res.collections else 0
        
        # Check if the underlying client is preferring grpc
        grpc_enabled = client._prefer_grpc if hasattr(client, "_prefer_grpc") else False
            
    except Exception as exc:
        logger.warning("Qdrant vector database health check failed", error=str(exc))
        QdrantMetrics.record_error()
        status = "unhealthy"
        error = str(exc)
        
    latency_ms = (time.perf_counter() - start) * 1000
    stats = QdrantMetrics.get_stats()
    
    return {
        "status": status,
        "latency_ms": round(latency_ms, 2),
        "collection_count": collection_count,
        "grpc_enabled": grpc_enabled,
        "retries": stats["retries"],
        "errors": stats["errors"],
        "error": error
    }


async def close_vector_db() -> None:
    """Close the Qdrant async client cleanly during application shutdown."""
    for loop, client in list(_state.clients.items()):
        logger.info("Closing AsyncQdrantClient", loop_id=id(loop))
        await client.close()
    _state.clients.clear()
    
    if _state.fallback_client:
        await _state.fallback_client.close()
        _state.fallback_client = None
