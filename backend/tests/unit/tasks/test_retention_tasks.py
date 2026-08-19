import datetime
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import pytest

from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.models.entities.workspace_settings import WorkspaceSettings
from backend.tasks.retention import _push_to_dlq, _run_chat_retention_sweep, _run_document_retention_sweep


@pytest.mark.asyncio
async def test_document_retention_sweep_success():
    ws_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    ws_mock = Workspace(id=ws_id, name="Test WS", slug="test-ws", status=WorkspaceStatus.ACTIVE.value)
    ws_settings = WorkspaceSettings(
        workspace_id=ws_id,
        settings_json={"general": {"retention_days": 30}},
    )

    mock_session = AsyncMock()

    # Mock fetch workspaces
    mock_ws_res = MagicMock()
    mock_ws_res.scalars.return_value.all.return_value = [ws_mock]

    # mock settings
    mock_s_res = MagicMock()
    mock_s_res.scalar_one_or_none.return_value = ws_settings

    # mock eligible documents
    mock_doc_res = MagicMock()
    mock_doc_res.all.return_value = [(doc_id, "test-ws")]

    mock_session.execute = AsyncMock(side_effect=[mock_ws_res, mock_s_res, mock_doc_res, AsyncMock(), AsyncMock()])
    mock_session.commit = AsyncMock()

    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_factory.return_value.__aexit__ = AsyncMock()

    with patch("backend.tasks.retention.get_session_factory", return_value=mock_factory), \
         patch("backend.tasks.retention.LocalStorageProvider") as mock_storage_cls, \
         patch("backend.tasks.retention.VectorStorageService") as mock_vector_cls:
        mock_storage = MagicMock()
        mock_storage.delete_prefix = AsyncMock()
        mock_storage_cls.return_value = mock_storage

        mock_vector = MagicMock()
        mock_vector.remove_archived_document_vectors = AsyncMock(return_value=1)
        mock_vector_cls.return_value = mock_vector

        result = await _run_document_retention_sweep()

        assert result["workspaces_evaluated"] == 1
        assert result["documents_soft_deleted"] == 1
        assert result["documents_hard_deleted"] == 1
        assert result["qdrant_cleaned"] == 1
        assert result["storage_cleaned"] == 1
        assert result["errors"] == 0
        mock_vector.remove_archived_document_vectors.assert_called_once_with(document_id=str(doc_id), tenant_id="test-ws")
        mock_storage.delete_prefix.assert_called_once_with(f'documents/test-ws/{doc_id}')


@pytest.mark.asyncio
async def test_chat_retention_sweep_exempts_pinned():
    ws_id = uuid.uuid4()
    session_id = str(uuid.uuid4())

    ws_mock = Workspace(id=ws_id, name="Test WS", slug="test-ws", status=WorkspaceStatus.ACTIVE.value)
    ws_settings = WorkspaceSettings(
        workspace_id=ws_id,
        settings_json={"general": {"retention_days": 90}},
    )

    mock_session = AsyncMock()

    mock_ws_res = MagicMock()
    mock_ws_res.scalars.return_value.all.return_value = [ws_mock]

    mock_s_res = MagicMock()
    mock_s_res.scalar_one_or_none.return_value = ws_settings

    mock_chat_res = MagicMock()
    mock_chat_res.all.return_value = [(session_id,)]

    mock_session.execute = AsyncMock(side_effect=[mock_ws_res, mock_s_res, mock_chat_res, AsyncMock()])
    mock_session.commit = AsyncMock()

    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_factory.return_value.__aexit__ = AsyncMock()

    with patch("backend.tasks.retention.get_session_factory", return_value=mock_factory):
        result = await _run_chat_retention_sweep()
        assert result["workspaces_evaluated"] == 1
        assert result["sessions_deleted"] == 1
        assert result["errors"] == 0


@pytest.mark.asyncio
async def test_retention_sweep_dlq_push_called():
    mock_redis = AsyncMock()
    mock_redis.rpush = AsyncMock()

    with patch("backend.tasks.retention.get_redis_client", return_value=mock_redis):
        await _push_to_dlq("test_task", {"key": "val"}, "Error details")
        mock_redis.rpush.assert_called_once()
        call_args = mock_redis.rpush.call_args[0]
        assert call_args[0] == "retention:dlq"
        assert "test_task" in call_args[1]
