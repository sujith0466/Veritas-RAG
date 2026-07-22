"""Cloud storage abstractions (S3, Azure Blob, GCS).

Prepared abstractions ready for cloud provider SDK adoption upon configuration toggle (`ADR-006`).
"""

from typing import Any, BinaryIO

from backend.document.schemas.errors import (DocumentDomainException,
                                             DocumentErrorCode)

from .base import StorageObjectDTO, StorageProvider


class S3StorageProvider(StorageProvider):
    """AWS S3 storage provider abstraction."""

    def __init__(self, bucket: str, region: str = "us-east-1") -> None:
        self._bucket = bucket
        self._region = region

    @property
    def provider_name(self) -> str:
        return "s3"

    @property
    def bucket_name(self) -> str:
        return self._bucket

    async def save_stream(self, stream: BinaryIO, object_key: str) -> StorageObjectDTO:
        raise DocumentDomainException(
            code=DocumentErrorCode.STORE_003,
            message="S3StorageProvider is prepared but requires boto3 configuration.",
            detail={"provider": "s3", "bucket": self._bucket},
        )

    async def save_bytes(self, content: bytes, object_key: str) -> StorageObjectDTO:
        raise NotImplementedError("S3 save_bytes not configured.")

    async def save_json(
        self, data: dict[str, Any], object_key: str
    ) -> StorageObjectDTO:
        raise NotImplementedError("S3 save_json not configured.")

    async def get_stream(self, object_key: str) -> BinaryIO:
        raise NotImplementedError("S3 get_stream not configured.")

    async def get_bytes(self, object_key: str) -> bytes:
        raise NotImplementedError("S3 get_bytes not configured.")

    async def get_json(self, object_key: str) -> dict[str, Any]:
        raise NotImplementedError("S3 get_json not configured.")

    async def delete_object(self, object_key: str) -> bool:
        raise NotImplementedError("S3 delete_object not configured.")

    async def delete_prefix(self, prefix: str) -> int:
        raise NotImplementedError("S3 delete_prefix not configured.")

    async def object_exists(self, object_key: str) -> bool:
        return False

    async def get_uri(self, object_key: str) -> str:
        return f"s3://{self._bucket}/{object_key}"


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
