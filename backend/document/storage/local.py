"""Local Storage Provider implementation (`LocalStorageProvider`).

Saves file artifacts to local filesystem volume directory while adhering strictly to `StorageProvider` interface.
"""

import io
import json
import os
from pathlib import Path
from typing import Any, BinaryIO

from backend.document.schemas.errors import DocumentDomainException, DocumentErrorCode
from backend.document.utils.hashing import calculate_sha256
from .base import StorageObjectDTO, StorageProvider


class LocalStorageProvider(StorageProvider):
    """Local volume filesystem storage implementation."""

    def __init__(self, root_path: str | Path = "storage") -> None:
        self.root = Path(root_path).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    @property
    def provider_name(self) -> str:
        return "local"

    @property
    def bucket_name(self) -> str:
        return str(self.root)

    def _resolve_path(self, object_key: str) -> Path:
        """Safely resolve object_key under root directory preventing path traversal."""
        clean_key = object_key.lstrip("/\\")
        full_path = (self.root / clean_key).resolve()
        if not str(full_path).startswith(str(self.root)):
            raise DocumentDomainException(
                code=DocumentErrorCode.STORE_001,
                message="Security violation: Storage path traversal attempt outside volume root.",
                detail={"object_key": object_key},
            )
        return full_path

    async def save_stream(self, stream: BinaryIO, object_key: str) -> StorageObjectDTO:
        target_path = self._resolve_path(object_key)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            current_pos = stream.tell()
            stream.seek(0)
            checksum = calculate_sha256(stream)
            stream.seek(0)

            size_bytes = 0
            with open(target_path, "wb") as f:
                while chunk := stream.read(65536):
                    f.write(chunk)
                    size_bytes += len(chunk)

            stream.seek(current_pos)
            return StorageObjectDTO(
                provider=self.provider_name,
                bucket_or_container=self.bucket_name,
                object_key=object_key,
                file_size_bytes=size_bytes,
                checksum_sha256=checksum,
            )
        except Exception as e:
            if isinstance(e, DocumentDomainException):
                raise
            raise DocumentDomainException(
                code=DocumentErrorCode.STORE_001,
                message=f"Failed to write object stream to local storage: {e}",
                detail={"object_key": object_key, "error": str(e)},
            ) from e

    async def save_bytes(self, content: bytes, object_key: str) -> StorageObjectDTO:
        stream = io.BytesIO(content)
        return await self.save_stream(stream, object_key)

    async def save_json(self, data: dict[str, Any], object_key: str) -> StorageObjectDTO:
        try:
            content = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
            return await self.save_bytes(content, object_key)
        except Exception as e:
            raise DocumentDomainException(
                code=DocumentErrorCode.STORE_001,
                message=f"Failed to serialize and save JSON object: {e}",
                detail={"object_key": object_key, "error": str(e)},
            ) from e

    async def get_stream(self, object_key: str) -> BinaryIO:
        target_path = self._resolve_path(object_key)
        if not target_path.exists() or not target_path.is_file():
            raise DocumentDomainException(
                code=DocumentErrorCode.STORE_002,
                message="Requested storage artifact was not found on local volume.",
                detail={"object_key": object_key},
            )
        try:
            with open(target_path, "rb") as f:
                content = f.read()
            return io.BytesIO(content)
        except Exception as e:
            raise DocumentDomainException(
                code=DocumentErrorCode.STORE_002,
                message=f"Failed to read artifact stream from storage: {e}",
                detail={"object_key": object_key, "error": str(e)},
            ) from e

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

    async def delete_object(self, object_key: str) -> bool:
        target_path = self._resolve_path(object_key)
        if target_path.exists() and target_path.is_file():
            try:
                target_path.unlink()
                return True
            except Exception as e:
                raise DocumentDomainException(
                    code=DocumentErrorCode.STORE_001,
                    message=f"Failed to delete artifact: {e}",
                    detail={"object_key": object_key, "error": str(e)},
                ) from e
        return True

    async def delete_prefix(self, prefix: str) -> int:
        clean_prefix = prefix.lstrip("/\\")
        prefix_dir = (self.root / clean_prefix).resolve()
        if not str(prefix_dir).startswith(str(self.root)) or not prefix_dir.exists():
            return 0

        deleted_count = 0
        if prefix_dir.is_file():
            prefix_dir.unlink()
            return 1

        for root_dir, _, files in os.walk(prefix_dir, topdown=False):
            for file in files:
                file_path = Path(root_dir) / file
                file_path.unlink(missing_ok=True)
                deleted_count += 1
            try:
                Path(root_dir).rmdir()
            except OSError:
                pass

        return deleted_count

    async def object_exists(self, object_key: str) -> bool:
        target_path = self._resolve_path(object_key)
        return target_path.exists() and target_path.is_file() and target_path.stat().st_size > 0

    async def get_uri(self, object_key: str) -> str:
        target_path = self._resolve_path(object_key)
        return target_path.as_uri()
