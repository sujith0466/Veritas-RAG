"""Unit tests for Qdrant vector database async client and health checks."""

import asyncio
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from qdrant_client import AsyncQdrantClient

from backend.vector_db.client import (
    check_vector_db_health,
    close_vector_db,
    get_qdrant_client,
    get_vector_db,
)


@pytest.fixture(autouse=True)
def reset_vector_db_singletons() -> Generator[None, None, None]:
    """Reset vector DB singletons cleanly before and after each test."""
    asyncio.run(close_vector_db())
    yield
    asyncio.run(close_vector_db())


@pytest.mark.unit
class TestQdrantClient:
    @patch("backend.vector_db.client.AsyncQdrantClient")
    def test_get_qdrant_client_singleton(self, mock_client_cls: MagicMock) -> None:
        mock_client = MagicMock(spec=AsyncQdrantClient)
        mock_client_cls.return_value = mock_client

        client1 = get_qdrant_client()
        client2 = get_qdrant_client()

        assert client1 is client2
        mock_client_cls.assert_called_once()

    @patch("backend.vector_db.client.AsyncQdrantClient")
    def test_get_qdrant_client_with_api_key(self, mock_client_cls: MagicMock) -> None:
        mock_client = MagicMock(spec=AsyncQdrantClient)
        mock_client_cls.return_value = mock_client

        with patch("backend.vector_db.client.get_settings") as mock_settings:
            mock_settings.return_value.qdrant.host = "qdrant.cloud"
            mock_settings.return_value.qdrant.port = 6333
            mock_settings.return_value.qdrant.grpc_port = 6334
            mock_settings.return_value.qdrant.prefer_grpc = True
            mock_settings.return_value.qdrant.api_key = "secret_key"
            mock_settings.return_value.qdrant.url_override = None

            get_qdrant_client()
            mock_client_cls.assert_called_once_with(
                host="qdrant.cloud",
                port=6333,
                prefer_grpc=True,
                api_key="secret_key",
            )

    @patch("backend.vector_db.client.get_qdrant_client")
    @pytest.mark.asyncio
    async def test_get_vector_db_dependency(self, mock_get_client: MagicMock) -> None:
        mock_client = MagicMock(spec=AsyncQdrantClient)
        mock_get_client.return_value = mock_client

        gen = get_vector_db()
        client = await anext(gen)
        assert client is mock_client

    @patch("backend.vector_db.client.get_qdrant_client")
    @pytest.mark.asyncio
    async def test_check_vector_db_health(self, mock_get_client: MagicMock) -> None:
        mock_client = AsyncMock(spec=AsyncQdrantClient)
        mock_get_client.return_value = mock_client

        assert await check_vector_db_health() is True
        mock_client.get_collections.assert_awaited_once()

        mock_client.get_collections.side_effect = Exception("Connection refused")
        assert await check_vector_db_health() is False

    @patch("backend.vector_db.client.AsyncQdrantClient")
    @pytest.mark.asyncio
    async def test_close_vector_db(self, mock_client_cls: MagicMock) -> None:
        mock_client = AsyncMock(spec=AsyncQdrantClient)
        mock_client_cls.return_value = mock_client

        get_qdrant_client()
        await close_vector_db()

        mock_client.close.assert_awaited_once()
