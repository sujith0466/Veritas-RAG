"""Unit tests for StoragePreflightValidator (Phase D2.4)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.document.storage.preflight import StoragePreflightValidator, PreflightResult


@pytest.fixture
def mock_storage_obj():
    obj = MagicMock()
    obj.storage_provider = "local"
    obj.bucket_or_container = "/app/data/storage"
    obj.object_key = "63e0de56-cb8a-45dd-a417-688f0c88ffbb/raw/test.txt"
    obj.size_bytes = 100
    return obj


def test_storage_preflight_valid_file(tmp_path, mock_storage_obj):
    """Test pre-flight succeeds when physical file exists and is readable."""
    tenant_id = "63e0de56-cb8a-45dd-a417-688f0c88ffbb"
    container_file = tmp_path / tenant_id / "raw" / "test.txt"
    container_file.parent.mkdir(parents=True, exist_ok=True)
    container_file.write_bytes(b"Valid container file")

    mock_storage_obj.bucket_or_container = "/app/data/storage"
    mock_storage_obj.object_key = f"{tenant_id}/raw/test.txt"

    with patch.object(StoragePreflightValidator, "CONTAINER_ROOT", tmp_path):
        result = StoragePreflightValidator.validate(mock_storage_obj, expected_tenant_id=tenant_id)

        assert result.is_valid is True
        assert result.error_code is None
        assert result.file_size_bytes == len(b"Valid container file")


def test_storage_preflight_missing_storage(tmp_path, mock_storage_obj):
    """Test pre-flight returns STORAGE_OBJECT_NOT_FOUND when file does not exist on disk."""
    mock_storage_obj.object_key = "63e0de56-cb8a-45dd-a417-688f0c88ffbb/non_existent.txt"

    with patch.object(StoragePreflightValidator, "CONTAINER_ROOT", tmp_path):
        result = StoragePreflightValidator.validate(
            mock_storage_obj,
            expected_tenant_id="63e0de56-cb8a-45dd-a417-688f0c88ffbb",
        )

        assert result.is_valid is False
        assert result.error_code == "STORAGE_OBJECT_NOT_FOUND"
        assert "does not exist" in result.error_message


def test_storage_preflight_historical_windows_path_anomaly(tmp_path, mock_storage_obj):
    """Test pre-flight flags historical D:\\app\\data\\storage path anomaly."""
    mock_storage_obj.bucket_or_container = r"D:\app\data\storage"
    mock_storage_obj.object_key = "63e0de56-cb8a-45dd-a417-688f0c88ffbb/historical.pdf"

    with patch.object(StoragePreflightValidator, "CONTAINER_ROOT", tmp_path):
        result = StoragePreflightValidator.validate(
            mock_storage_obj,
            expected_tenant_id="63e0de56-cb8a-45dd-a417-688f0c88ffbb",
        )

        assert result.is_valid is False
        assert result.error_code == "STORAGE_OBJECT_NOT_FOUND"
        assert result.anomaly_type == "HISTORICAL_WINDOWS_PATH"


def test_storage_preflight_malformed_key(mock_storage_obj):
    """Test pre-flight detects empty keys and path traversal."""
    mock_storage_obj.object_key = ""
    res1 = StoragePreflightValidator.validate(mock_storage_obj)
    assert res1.is_valid is False
    assert res1.error_code == "MALFORMED_STORAGE_KEY"

    mock_storage_obj.object_key = "tenant-1/../../etc/passwd"
    res2 = StoragePreflightValidator.validate(mock_storage_obj)
    assert res2.is_valid is False
    assert res2.error_code == "PATH_TRAVERSAL_DETECTED"


def test_storage_preflight_tenant_isolation(mock_storage_obj):
    """Test pre-flight enforces strict tenant namespace matching."""
    mock_storage_obj.object_key = "11111111-1111-1111-1111-111111111111/raw/doc.txt"
    different_tenant = "22222222-2222-2222-2222-222222222222"

    result = StoragePreflightValidator.validate(
        mock_storage_obj,
        expected_tenant_id=different_tenant,
    )

    assert result.is_valid is False
    assert result.error_code == "TENANT_ISOLATION_VIOLATION"


def test_storage_preflight_unreadable_file(tmp_path, mock_storage_obj):
    """Test pre-flight detects unreadable / permission denied files."""
    tenant_id = "63e0de56-cb8a-45dd-a417-688f0c88ffbb"
    container_file = tmp_path / tenant_id / "raw" / "test.txt"
    container_file.parent.mkdir(parents=True, exist_ok=True)
    container_file.write_bytes(b"content")

    mock_storage_obj.bucket_or_container = "/app/data/storage"
    mock_storage_obj.object_key = f"{tenant_id}/raw/test.txt"

    with patch.object(StoragePreflightValidator, "CONTAINER_ROOT", tmp_path):
        with patch("builtins.open", side_effect=PermissionError("Permission denied")):
            result = StoragePreflightValidator.validate(mock_storage_obj, expected_tenant_id=tenant_id)

            assert result.is_valid is False
            assert result.error_code == "OBJECT_UNREADABLE"
            assert "Permission denied" in result.error_message
