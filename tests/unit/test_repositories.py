"""Unit tests for generic BaseRepository and concrete entity repositories."""

from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import AuditLog, User
from backend.repositories import AuditLogRepository, BaseRepository, UserRepository


@pytest.mark.unit
class TestBaseRepository:
    @pytest.mark.asyncio
    async def test_get_by_id(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_user = User(email="test@raguard.ai")
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result

        repo = BaseRepository(mock_session, User)
        found = await repo.get_by_id(mock_user.id)

        assert found is mock_user
        mock_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_all(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_users = [User(email="u1@raguard.ai"), User(email="u2@raguard.ai")]
        mock_result.scalars.return_value.all.return_value = mock_users
        mock_session.execute.return_value = mock_result

        repo = BaseRepository(mock_session, User)
        found = await repo.get_all(skip=10, limit=5)

        assert found == mock_users
        mock_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        repo = BaseRepository(mock_session, User)

        created = await repo.create(email="new@raguard.ai", role="admin")
        assert created.email == "new@raguard.ai"
        assert created.role == "admin"
        mock_session.add.assert_called_once_with(created)
        mock_session.flush.assert_awaited_once()
        mock_session.refresh.assert_awaited_once_with(created)

    @pytest.mark.asyncio
    async def test_update(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        repo = BaseRepository(mock_session, User)
        user = User(email="old@raguard.ai", role="viewer")

        updated = await repo.update(user, role="superadmin")
        assert updated.role == "superadmin"
        mock_session.flush.assert_awaited_once()
        mock_session.refresh.assert_awaited_once_with(user)

    @pytest.mark.asyncio
    async def test_soft_delete(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        repo = BaseRepository(mock_session, User)
        user = User(email="delete@raguard.ai", is_deleted=False)
        assert user.is_deleted is False

        await repo.soft_delete(user)
        assert user.is_deleted is True
        mock_session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_hard_delete(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        repo = BaseRepository(mock_session, User)
        user = User(email="purge@raguard.ai")

        await repo.hard_delete(user)
        mock_session.delete.assert_awaited_once_with(user)
        mock_session.flush.assert_awaited_once()


@pytest.mark.unit
class TestConcreteRepositories:
    @pytest.mark.asyncio
    async def test_user_repository_get_by_email(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_user = User(email="admin@raguard.ai")
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result

        repo = UserRepository(mock_session)
        found = await repo.get_by_email("admin@raguard.ai")
        assert found is mock_user
        mock_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_user_repository_get_by_supabase_id(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_user = User(email="auth@raguard.ai", supabase_user_id="sub_123")
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result

        repo = UserRepository(mock_session)
        found = await repo.get_by_supabase_id("sub_123")
        assert found is mock_user

    @pytest.mark.asyncio
    async def test_audit_log_repository_filters(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_logs = [AuditLog(action="LOGIN")]
        mock_result.scalars.return_value.all.return_value = mock_logs
        mock_session.execute.return_value = mock_result

        repo = AuditLogRepository(mock_session)
        found_by_action = await repo.get_by_action("LOGIN")
        assert found_by_action == mock_logs

        found_by_user = await repo.get_by_user_id(uuid.uuid4())
        assert found_by_user == mock_logs
        assert mock_session.execute.await_count == 2
