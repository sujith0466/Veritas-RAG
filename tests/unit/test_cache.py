"""Unit tests for Redis cache client and connection pooling."""

import asyncio
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.asyncio import ConnectionPool, Redis

from backend.cache.client import (
    check_cache_health,
    close_cache,
    get_cache,
    get_redis_client,
    get_redis_pool,
)


@pytest.fixture(autouse=True)
def reset_cache_singletons() -> Generator[None, None, None]:
    """Reset cache singletons cleanly before and after each test."""
    asyncio.run(close_cache())
    yield
    asyncio.run(close_cache())


@pytest.mark.unit
class TestRedisCacheClient:
    @patch("backend.cache.client.ConnectionPool.from_url")
    def test_get_redis_pool_singleton(self, mock_from_url: MagicMock) -> None:
        mock_pool = MagicMock(spec=ConnectionPool)
        mock_from_url.return_value = mock_pool

        pool1 = get_redis_pool()
        pool2 = get_redis_pool()

        assert pool1 is pool2
        mock_from_url.assert_called_once()

    @patch("backend.cache.client.Redis")
    @patch("backend.cache.client.get_redis_pool")
    def test_get_redis_client_singleton(self, mock_get_pool: MagicMock, mock_redis: MagicMock) -> None:
        mock_pool = MagicMock(spec=ConnectionPool)
        mock_get_pool.return_value = mock_pool
        mock_client = MagicMock(spec=Redis)
        mock_redis.return_value = mock_client

        client1 = get_redis_client()
        client2 = get_redis_client()

        assert client1 is client2
        mock_redis.assert_called_once_with(connection_pool=mock_pool)

    @patch("backend.cache.client.get_redis_client")
    @pytest.mark.asyncio
    async def test_get_cache_dependency(self, mock_get_client: MagicMock) -> None:
        mock_client = MagicMock(spec=Redis)
        mock_get_client.return_value = mock_client

        gen = get_cache()
        client = await anext(gen)
        assert client is mock_client

    @patch("backend.cache.client.get_redis_client")
    @pytest.mark.asyncio
    async def test_check_cache_health(self, mock_get_client: MagicMock) -> None:
        mock_client = AsyncMock(spec=Redis)
        mock_get_client.return_value = mock_client

        mock_client.ping = AsyncMock(return_value=True)
        assert await check_cache_health() is True

        mock_client.ping = AsyncMock(return_value="PONG")
        assert await check_cache_health() is True

        mock_client.ping = AsyncMock(side_effect=Exception("Connection refused"))
        assert await check_cache_health() is False

    @patch("backend.cache.client.ConnectionPool.from_url")
    @patch("backend.cache.client.Redis")
    @pytest.mark.asyncio
    async def test_close_cache(self, mock_redis: MagicMock, mock_from_url: MagicMock) -> None:
        mock_pool = AsyncMock(spec=ConnectionPool)
        mock_from_url.return_value = mock_pool
        mock_client = AsyncMock(spec=Redis)
        mock_redis.return_value = mock_client

        get_redis_client()
        await close_cache()

        mock_client.close.assert_awaited_once()
        mock_pool.disconnect.assert_awaited_once()
