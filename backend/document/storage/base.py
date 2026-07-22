"""Abstract Storage Provider interface and versioned path helpers.

Enforces provider independence (`ADR-006`) and strict versioned directory layout.
"""

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, BinaryIO


@dataclass
class StorageObjectDTO:
    """Data transfer object representing a stored physical artifact."""

    provider: str
    bucket_or_container: str
    object_key: str
    file_size_bytes: int
    checksum_sha256: str


def get_versioned_path(
    tenant_id: str,
    document_id: str | uuid.UUID,
    version_number: int,
    category: str,
    filename: str,
) -> str:
    """Generate canonical versioned object key (`documents/{tenant_id}/{document_id}/v{version}/{category}/{filename}`).

    Categories:
        - original   : Raw binary upload artifact
        - normalized : NFC UTF-8 text (`text.txt`)
        - metadata   : Canonical (`manifest.json`) & structured (`extraction.json`)
        - artifacts  : Future chunking/preview assets
    """
    return (
        f"documents/{tenant_id}/{document_id}/v{version_number}/{category}/{filename}"
    )


class StorageProvider(ABC):
    """Abstract interface isolating all physical object storage operations."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the storage provider (e.g., 'local', 's3', 'azure_blob')."""
        ...

    @property
    @abstractmethod
    def bucket_name(self) -> str:
        """Configured storage bucket or root directory."""
        ...

    @abstractmethod
    async def save_stream(self, stream: BinaryIO, object_key: str) -> StorageObjectDTO:
        """Save a binary stream to object storage at `object_key`."""
        ...

    @abstractmethod
    async def save_bytes(self, content: bytes, object_key: str) -> StorageObjectDTO:
        """Save raw bytes to object storage at `object_key`."""
        ...

    @abstractmethod
    async def save_json(
        self, data: dict[str, Any], object_key: str
    ) -> StorageObjectDTO:
        """Serialize and save JSON dictionary to `object_key`."""
        ...

    @abstractmethod
    async def get_stream(self, object_key: str) -> BinaryIO:
        """Retrieve binary stream for `object_key` (`STORE_002` if missing)."""
        ...

    @abstractmethod
    async def get_bytes(self, object_key: str) -> bytes:
        """Retrieve raw bytes for `object_key` (`STORE_002` if missing)."""
        ...

    @abstractmethod
    async def get_json(self, object_key: str) -> dict[str, Any]:
        """Retrieve and parse JSON dictionary from `object_key` (`STORE_002` if missing)."""
        ...

    @abstractmethod
    async def delete_object(self, object_key: str) -> bool:
        """Delete object at `object_key`. Returns True if deleted or did not exist."""
        ...

    @abstractmethod
    async def delete_prefix(self, prefix: str) -> int:
        """Delete all objects matching `prefix` (used during document deletion). Returns count."""
        ...

    @abstractmethod
    async def object_exists(self, object_key: str) -> bool:
        """Check if physical artifact exists at `object_key`."""
        ...

    @abstractmethod
    async def get_uri(self, object_key: str) -> str:
        """Get accessible URI or file path for `object_key`."""
        ...
