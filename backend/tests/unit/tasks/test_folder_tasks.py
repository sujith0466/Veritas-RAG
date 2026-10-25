"""Unit tests for folder Celery tasks and retention cron."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import pytest

from backend.services.folder_service import FolderService
from backend.tasks.folders import (
    _run_folder_retention_cron,
    cascade_move_subtree,
    cascade_restore_subtree,
    cascade_soft_delete_subtree,
    hard_delete_folder_subtree,
    run_folder_retention_cron,
)


def test_folder_service_repository_property():
    """Verify FolderService provides .repository as an alias to .repo."""
    mock_session = AsyncMock()
    mock_dispatcher = MagicMock()
    service = FolderService(session=mock_session, dispatcher=mock_dispatcher)
    assert hasattr(service, "repo")
    assert hasattr(service, "repository")
    assert service.repository is service.repo


@pytest.mark.asyncio
async def test_run_folder_retention_cron_service_contract():
    """Verify folder retention task instantiates FolderService with session and dispatcher only."""
    mock_session = AsyncMock()
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock()

    mock_result = {"scheduled_for_purge": 3, "failed": 0}

    with patch("backend.tasks.folders.SessionLocal", mock_session_factory), \
         patch("backend.services.folder_service.FolderService") as mock_service_cls, \
         patch("backend.services.folder.retention_worker.FolderRetentionWorker") as mock_worker_cls:

        mock_worker = MagicMock()
        mock_worker.run_retention_cleanup = AsyncMock(return_value=mock_result)
        mock_worker_cls.return_value = mock_worker

        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service

        task_self = MagicMock()
        res = await _run_folder_retention_cron(task_self)

        assert res == mock_result
        mock_service_cls.assert_called_once()
        _, kwargs = mock_service_cls.call_args
        assert kwargs["session"] is mock_session
        assert "dispatcher" in kwargs
        assert "repo" not in kwargs, "FolderService should not receive unexpected 'repo' argument"
        mock_worker_cls.assert_called_once_with(folder_service=mock_service)
        mock_worker.run_retention_cleanup.assert_called_once_with(mock_session, limit=50)


def test_run_folder_retention_cron_sync_entry_point():
    """Verify synchronous Celery task executes without requiring a pre-existing event loop."""
    asyncio.set_event_loop(None)

    mock_result = {"scheduled_for_purge": 0, "failed": 0}

    with patch("backend.tasks.folders._run_folder_retention_cron", new_callable=AsyncMock) as mock_async_fn:
        mock_async_fn.return_value = mock_result

        # Celery bound task injects task instance automatically when invoked as a function
        res = run_folder_retention_cron()

        assert res == mock_result
        assert mock_async_fn.called


def test_cascade_tasks_execute_without_event_loop():
    """Verify cascade tasks run without requiring a pre-existing event loop on the thread."""
    asyncio.set_event_loop(None)

    ws_id = str(uuid.uuid4())
    f_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    with patch("backend.tasks.folders._cascade_soft_delete_subtree", new_callable=AsyncMock) as m_soft, \
         patch("backend.tasks.folders._cascade_restore_subtree", new_callable=AsyncMock) as m_restore, \
         patch("backend.tasks.folders._cascade_move_subtree", new_callable=AsyncMock) as m_move, \
         patch("backend.tasks.folders._hard_delete_folder_subtree", new_callable=AsyncMock) as m_hard:

        m_soft.return_value = 1
        m_restore.return_value = 1
        m_move.return_value = 1
        m_hard.return_value = None

        assert cascade_soft_delete_subtree(f_id, ws_id, user_id, "2026-10-25T00:00:00") == 1
        assert cascade_restore_subtree(f_id, ws_id, user_id) == 1
        assert cascade_move_subtree(f_id, ws_id, "/old", "/new", 0, user_id) == 1
        assert hard_delete_folder_subtree(f_id, ws_id) is None
