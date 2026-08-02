"""Unit tests for database infrastructure and SQLAlchemy 2.x async engine."""

import asyncio
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from backend.database.engine import (
    check_db_health,
    close_db,
    get_async_session,
    get_engine,
    get_session_factory,
)
from backend.database.init_db import init_db


@pytest.fixture(autouse=True)
def reset_db_singletons() -> Generator[None, None, None]:
    """Ensure database singletons are cleanly closed before and after tests."""
    asyncio.run(close_db())
    yield
    asyncio.run(close_db())


@pytest.mark.unit
class TestDatabaseEngine:
    @patch("backend.database.engine.create_async_engine")
    def test_get_engine_singleton(self, mock_create: MagicMock) -> None:
        mock_engine = MagicMock(spec=AsyncEngine)
        mock_create.return_value = mock_engine

        engine1 = get_engine()
        engine2 = get_engine()

        assert engine1 is engine2
        mock_create.assert_called_once()

    @patch("backend.database.engine.create_async_engine")
    def test_get_session_factory_singleton(self, mock_create: MagicMock) -> None:
        mock_engine = MagicMock(spec=AsyncEngine)
        mock_create.return_value = mock_engine

        factory1 = get_session_factory()
        factory2 = get_session_factory()

        assert factory1 is factory2

    @patch("backend.database.engine.create_async_engine")
    @pytest.mark.asyncio
    async def test_close_db_disposes_engine(self, mock_create: MagicMock) -> None:
        mock_engine = AsyncMock(spec=AsyncEngine)
        mock_create.return_value = mock_engine

        get_engine()
        await close_db()

        mock_engine.dispose.assert_awaited_once()

    @patch("backend.database.engine.get_session_factory")
    @pytest.mark.asyncio
    async def test_get_async_session_yields_and_closes(self, mock_get_factory: MagicMock) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.__aenter__.return_value = mock_session
        mock_maker = MagicMock()
        mock_maker.return_value = mock_session
        mock_get_factory.return_value = mock_maker

        gen = get_async_session()
        session = await anext(gen)
        assert session is mock_session

        try:
            await anext(gen)
        except StopAsyncIteration:
            pass

        mock_session.close.assert_awaited_once()

    @patch("backend.database.engine.get_session_factory")
    @pytest.mark.asyncio
    async def test_get_async_session_rollback_on_error(self, mock_get_factory: MagicMock) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.__aenter__.return_value = mock_session
        mock_maker = MagicMock()
        mock_maker.return_value = mock_session
        mock_get_factory.return_value = mock_maker

        gen = get_async_session()
        await anext(gen)

        with pytest.raises(RuntimeError):
            await gen.athrow(RuntimeError("DB query failure"))

        mock_session.rollback.assert_awaited_once()
        mock_session.close.assert_awaited_once()

    @patch("backend.database.engine.get_engine")
    @pytest.mark.asyncio
    async def test_check_db_health(self, mock_get_engine: MagicMock) -> None:
        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_engine.connect.return_value.__aenter__.return_value = mock_conn
        mock_get_engine.return_value = mock_engine

        assert await check_db_health() is True
        mock_conn.execute.assert_awaited_once()

        mock_conn.execute.side_effect = Exception("Connection refused")
        assert await check_db_health() is False


@pytest.mark.unit
class TestInitDb:
    @patch("backend.database.init_db.get_engine")
    @pytest.mark.asyncio
    async def test_init_db_testing_mode(self, mock_get_engine: MagicMock) -> None:
        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_engine.begin.return_value.__aenter__.return_value = mock_conn
        mock_get_engine.return_value = mock_engine

        await init_db()
        mock_conn.run_sync.assert_awaited_once()
