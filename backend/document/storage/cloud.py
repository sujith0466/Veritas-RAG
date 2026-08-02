"""Cloud storage abstractions (S3, Azure Blob, GCS).

Prepared abstractions ready for cloud provider SDK adoption upon configuration toggle (`ADR-006`).
"""

import io
import json
import time
from typing import Any, BinaryIO

try:
    import aioboto3
    from botocore.config import Config
    import botocore.exceptions
except ImportError:
    aioboto3 = None
    Config = None
    class _DummyExceptions:
        class BotoCoreError(Exception): pass
        class ClientError(Exception): pass
    class _DummyBotocore:
        exceptions = _DummyExceptions
    botocore = _DummyBotocore()

from backend.core.utils.retry import with_retry
from backend.document.schemas.errors import DocumentDomainException, DocumentErrorCode
from backend.document.storage.metrics import StorageMetrics
from backend.document.utils.hashing import calculate_sha256

from .base import StorageObjectDTO, StorageProvider


class S3StorageProvider(StorageProvider):
    """AWS S3 storage provider abstraction using aioboto3."""

    def __init__(self, bucket: str, region: str = "us-east-1", endpoint_url: str | None = None) -> None:
        self._bucket = bucket
        self._region = region
        self._endpoint_url = endpoint_url
        self._session = aioboto3.Session()
        self._config = Config(
            retries={"max_attempts": 0},  # We handle retries via our with_retry utility
            connect_timeout=5,
            read_timeout=15,
        )

    @property
    def provider_name(self) -> str:
        return "s3"

    @property
    def bucket_name(self) -> str:
        return self._bucket

    def _handle_boto_error(self, e: Exception, object_key: str) -> None:
        """Filter exceptions: re-raise transient faults, fail fast on deterministic errors."""
        if isinstance(e, botocore.exceptions.ClientError):
            error_code = e.response.get("Error", {}).get("Code", "")
            # Deterministic errors that should NEVER be retried
            if error_code in ["AccessDenied", "InvalidAccessKeyId", "SignatureDoesNotMatch", "NoSuchBucket"]:
                StorageMetrics.record_failure()
                raise DocumentDomainException(
                    code=DocumentErrorCode.STORE_001,
                    message=f"S3 access denied or configuration invalid: {error_code}",
                    detail={"object_key": object_key, "error": str(e)},
                ) from e
            if error_code == "NoSuchKey":
                raise DocumentDomainException(
                    code=DocumentErrorCode.STORE_002,
                    message="Requested storage artifact was not found.",
                    detail={"object_key": object_key},
                ) from e

        # Other errors like EndpointConnectionError are transient and will be caught by with_retry.
        raise e

    @with_retry(
        max_retries=3,
        exceptions=(botocore.exceptions.BotoCoreError, botocore.exceptions.ClientError),
        base_delay=1.0,
    )
    async def save_stream(self, stream: BinaryIO, object_key: str) -> StorageObjectDTO:
        start_time = time.perf_counter()

        current_pos = stream.tell()
        stream.seek(0)
        checksum = calculate_sha256(stream)
        stream.seek(0)

        # Calculate size
        stream.seek(0, 2)
        size_bytes = stream.tell()
        stream.seek(0)

        try:
            async with self._session.client(
                "s3",
                region_name=self._region,
                endpoint_url=self._endpoint_url,
                config=self._config
            ) as client:
                await client.put_object(
                    Bucket=self._bucket,
                    Key=object_key,
                    Body=stream,
                )
        except Exception as e:
            self._handle_boto_error(e, object_key)

        latency_ms = (time.perf_counter() - start_time) * 1000
        StorageMetrics.record_upload(size_bytes, latency_ms)

        stream.seek(current_pos)
        return StorageObjectDTO(
            provider=self.provider_name,
            bucket_or_container=self.bucket_name,
            object_key=object_key,
            file_size_bytes=size_bytes,
            checksum_sha256=checksum,
        )

    async def save_bytes(self, content: bytes, object_key: str) -> StorageObjectDTO:
        return await self.save_stream(io.BytesIO(content), object_key)

    async def save_json(self, data: dict[str, Any], object_key: str) -> StorageObjectDTO:
        content = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
        return await self.save_bytes(content, object_key)

    @with_retry(
        max_retries=3,
        exceptions=(botocore.exceptions.BotoCoreError, botocore.exceptions.ClientError),
        base_delay=1.0,
    )
    async def get_stream(self, object_key: str) -> BinaryIO:
        start_time = time.perf_counter()
        try:
            async with self._session.client(
                "s3",
                region_name=self._region,
                endpoint_url=self._endpoint_url,
                config=self._config
            ) as client:
                response = await client.get_object(Bucket=self._bucket, Key=object_key)
                body = await response["Body"].read()

                latency_ms = (time.perf_counter() - start_time) * 1000
                StorageMetrics.record_download(len(body), latency_ms)

                return io.BytesIO(body)
        except Exception as e:
            self._handle_boto_error(e, object_key)

    async def get_bytes(self, object_key: str) -> bytes:
        stream = await self.get_stream(object_key)
        return stream.read()

    async def get_json(self, object_key: str) -> dict[str, Any]:
        content = await self.get_bytes(object_key)
        try:
            return json.loads(content.decode("utf-8"))
        except Exception as e:
            raise DocumentDomainException(
                code=DocumentErrorCode.STORE_002,
                message=f"Artifact at '{object_key}' is corrupted or invalid JSON: {e}",
                detail={"object_key": object_key, "error": str(e)},
            ) from e

    @with_retry(
        max_retries=3,
        exceptions=(botocore.exceptions.BotoCoreError, botocore.exceptions.ClientError),
        base_delay=1.0,
    )
    async def delete_object(self, object_key: str) -> bool:
        try:
            async with self._session.client(
                "s3",
                region_name=self._region,
                endpoint_url=self._endpoint_url,
                config=self._config
            ) as client:
                await client.delete_object(Bucket=self._bucket, Key=object_key)
                StorageMetrics.record_delete()
                return True
        except Exception as e:
            self._handle_boto_error(e, object_key)

    @with_retry(
        max_retries=3,
        exceptions=(botocore.exceptions.BotoCoreError, botocore.exceptions.ClientError),
        base_delay=1.0,
    )
    async def delete_prefix(self, prefix: str) -> int:
        deleted_count = 0
        try:
            async with self._session.client(
                "s3",
                region_name=self._region,
                endpoint_url=self._endpoint_url,
                config=self._config
            ) as client:
                paginator = client.get_paginator("list_objects_v2")
                async for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
                    if "Contents" in page:
                        objects = [{"Key": obj["Key"]} for obj in page["Contents"]]
                        if objects:
                            await client.delete_objects(
                                Bucket=self._bucket,
                                Delete={"Objects": objects, "Quiet": True}
                            )
                            deleted_count += len(objects)
                            for _ in objects:
                                StorageMetrics.record_delete()
        except Exception as e:
            self._handle_boto_error(e, prefix)
        return deleted_count

    async def object_exists(self, object_key: str) -> bool:
        try:
            async with self._session.client(
                "s3",
                region_name=self._region,
                endpoint_url=self._endpoint_url,
                config=self._config
            ) as client:
                await client.head_object(Bucket=self._bucket, Key=object_key)
                return True
        except botocore.exceptions.ClientError as e:
            if e.response.get("Error", {}).get("Code", "") == "404":
                return False
            raise e

    async def get_uri(self, object_key: str) -> str:
        return f"s3://{self._bucket}/{object_key}"

    async def create_upload_url(self, object_key: str, expiration_seconds: int = 3600) -> str:
        try:
            async with self._session.client(
                "s3",
                region_name=self._region,
                endpoint_url=self._endpoint_url,
                config=self._config
            ) as client:
                url = await client.generate_presigned_url(
                    ClientMethod="put_object",
                    Params={"Bucket": self._bucket, "Key": object_key},
                    ExpiresIn=expiration_seconds,
                )
                return url
        except Exception as e:
            self._handle_boto_error(e, object_key)

    async def create_download_url(self, object_key: str, expiration_seconds: int = 3600) -> str:
        try:
            async with self._session.client(
                "s3",
                region_name=self._region,
                endpoint_url=self._endpoint_url,
                config=self._config
            ) as client:
                url = await client.generate_presigned_url(
                    ClientMethod="get_object",
                    Params={"Bucket": self._bucket, "Key": object_key},
                    ExpiresIn=expiration_seconds,
                )
                return url
        except Exception as e:
            self._handle_boto_error(e, object_key)


class AzureBlobStorageProvider(StorageProvider):
    """Azure Blob Storage abstraction."""

    def __init__(self, container: str) -> None:
        self._container = container

    @property
    def provider_name(self) -> str:
        return "azure_blob"

    @property
    def bucket_name(self) -> str:
        return self._container

    async def save_stream(self, stream: BinaryIO, object_key: str) -> StorageObjectDTO:
        raise NotImplementedError("Azure Blob save_stream not configured.")

    async def save_bytes(self, content: bytes, object_key: str) -> StorageObjectDTO:
        raise NotImplementedError("Azure Blob save_bytes not configured.")

    async def save_json(
        self, data: dict[str, Any], object_key: str
    ) -> StorageObjectDTO:
        raise NotImplementedError("Azure Blob save_json not configured.")

    async def get_stream(self, object_key: str) -> BinaryIO:
        raise NotImplementedError("Azure Blob get_stream not configured.")

    async def get_bytes(self, object_key: str) -> bytes:
        raise NotImplementedError("Azure Blob get_bytes not configured.")

    async def get_json(self, object_key: str) -> dict[str, Any]:
        raise NotImplementedError("Azure Blob get_json not configured.")

    async def delete_object(self, object_key: str) -> bool:
        raise NotImplementedError("Azure Blob delete_object not configured.")

    async def delete_prefix(self, prefix: str) -> int:
        raise NotImplementedError("Azure Blob delete_prefix not configured.")

    async def object_exists(self, object_key: str) -> bool:
        return False

    async def get_uri(self, object_key: str) -> str:
        return f"https://{self._container}.blob.core.windows.net/{object_key}"


class GCSStorageProvider(StorageProvider):
    """Google Cloud Storage abstraction."""

    def __init__(self, bucket: str) -> None:
        self._bucket = bucket

    @property
    def provider_name(self) -> str:
        return "gcs"

    @property
    def bucket_name(self) -> str:
        return self._bucket

    async def save_stream(self, stream: BinaryIO, object_key: str) -> StorageObjectDTO:
        raise NotImplementedError("GCS save_stream not configured.")

    async def save_bytes(self, content: bytes, object_key: str) -> StorageObjectDTO:
        raise NotImplementedError("GCS save_bytes not configured.")

    async def save_json(
        self, data: dict[str, Any], object_key: str
    ) -> StorageObjectDTO:
        raise NotImplementedError("GCS save_json not configured.")

    async def get_stream(self, object_key: str) -> BinaryIO:
        raise NotImplementedError("GCS get_stream not configured.")

    async def get_bytes(self, object_key: str) -> bytes:
        raise NotImplementedError("GCS get_bytes not configured.")

    async def get_json(self, object_key: str) -> dict[str, Any]:
        raise NotImplementedError("GCS get_json not configured.")

    async def delete_object(self, object_key: str) -> bool:
        raise NotImplementedError("GCS delete_object not configured.")

    async def delete_prefix(self, prefix: str) -> int:
        raise NotImplementedError("GCS delete_prefix not configured.")

    async def object_exists(self, object_key: str) -> bool:
        return False

    async def get_uri(self, object_key: str) -> str:
        return f"gs://{self._bucket}/{object_key}"
