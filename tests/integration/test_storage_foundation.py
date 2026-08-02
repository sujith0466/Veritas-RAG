"""Integration tests for Object Storage Foundation capabilities.

Tests BucketNameBuilder, StorageMetrics, StorageProviderFactory, and S3StorageProvider logic.
"""

import io
import pytest
from typing import Any

import botocore.exceptions
from botocore.config import Config

from backend.document.storage.cloud import S3StorageProvider
from backend.document.storage.factory import StorageProviderFactory
from backend.document.storage.local import LocalStorageProvider
from backend.document.storage.metrics import StorageMetrics
from backend.document.storage.utils import BucketNameBuilder
from backend.document.storage.init import initialize_buckets
from backend.document.schemas.errors import DocumentDomainException


def test_bucket_name_builder():
    """Test consistent bucket naming strategies."""
    # Assuming defaults in test environment
    assert BucketNameBuilder.build_document_bucket() == "raguard-documents"
    assert BucketNameBuilder.build_audit_bucket() == "raguard-audit-logs"


def test_storage_provider_factory():
    """Test resolution of Storage Provider."""
    provider = StorageProviderFactory.get_provider()
    # By default, in dev/test it resolves to LocalStorageProvider
    assert isinstance(provider, LocalStorageProvider)
    assert provider.provider_name == "local"


@pytest.mark.asyncio
async def test_storage_metrics_singleton():
    """Test throughput and latency aggregation in metrics."""
    # Reset stats
    StorageMetrics._upload_count = 0
    StorageMetrics._download_count = 0
    StorageMetrics._bytes_uploaded = 0
    StorageMetrics._bytes_downloaded = 0
    StorageMetrics._upload_latency = 0.0
    StorageMetrics._download_latency = 0.0
    StorageMetrics._delete_count = 0
    StorageMetrics._retries = 0
    StorageMetrics._failures = 0

    StorageMetrics.record_upload(bytes_count=1024, latency_ms=50.0)
    StorageMetrics.record_download(bytes_count=512, latency_ms=25.0)
    StorageMetrics.record_download(bytes_count=512, latency_ms=15.0)
    StorageMetrics.record_delete()
    StorageMetrics.record_failure()

    stats = StorageMetrics.get_stats()
    assert stats["upload_count"] == 1
    assert stats["bytes_uploaded"] == 1024
    assert stats["avg_upload_latency_ms"] == 50.0
    assert stats["download_count"] == 2
    assert stats["bytes_downloaded"] == 1024
    assert stats["avg_download_latency_ms"] == 20.0
    assert stats["delete_count"] == 1
    assert stats["failures"] == 1


@pytest.mark.asyncio
async def test_s3_storage_provider_logic(mocker: Any):
    """Test S3 provider methods and resilient exception handling."""
    mock_session = mocker.patch("aioboto3.Session")
    mock_client = mocker.AsyncMock()
    mock_session.return_value.client.return_value.__aenter__.return_value = mock_client

    provider = S3StorageProvider(bucket="test-bucket")
    
    # 1. Test successful upload
    stream = io.BytesIO(b"test data")
    dto = await provider.save_stream(stream, "test-key.txt")
    assert dto.file_size_bytes == 9
    mock_client.put_object.assert_called_once()
    
    # 2. Test successful presigned URL
    mock_client.generate_presigned_url.return_value = "https://mock.url"
    url = await provider.create_upload_url("test-key.txt")
    assert url == "https://mock.url"
    mock_client.generate_presigned_url.assert_called_once()

    # 3. Test deterministic exception filtering (AccessDenied)
    error_response = {"Error": {"Code": "AccessDenied", "Message": "Denied"}}
    mock_client.get_object.side_effect = botocore.exceptions.ClientError(error_response, "GetObject")
    
    with pytest.raises(DocumentDomainException) as exc:
        await provider.get_stream("denied-key.txt")
    assert exc.value.code.name == "STORE_001"


@pytest.mark.asyncio
async def test_bucket_initialization(mocker: Any):
    """Test idempotent bucket init and WORM policy."""
    mock_session = mocker.patch("aioboto3.Session")
    mock_client = mocker.AsyncMock()
    mock_session.return_value.client.return_value.__aenter__.return_value = mock_client

    await initialize_buckets()

    # Should create two buckets (documents and audit)
    assert mock_client.create_bucket.call_count == 2
    
    # Should enable versioning on both
    assert mock_client.put_bucket_versioning.call_count == 2
    
    # Should apply object lock ONLY to the audit bucket
    mock_client.put_object_lock_configuration.assert_called_once()
    
    # Test idempotency handling
    error_response = {"Error": {"Code": "BucketAlreadyExists", "Message": "Exists"}}
    mock_client.create_bucket.side_effect = botocore.exceptions.ClientError(error_response, "CreateBucket")
    
    # Should not raise exception
    await initialize_buckets()
