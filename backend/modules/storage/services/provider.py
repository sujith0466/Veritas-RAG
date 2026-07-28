import os
import shutil
import uuid
from abc import ABC, abstractmethod
from typing import BinaryIO
from pathlib import Path


class StorageProvider(ABC):
    """Abstract base class for storage providers."""

    @abstractmethod
    async def upload_file(self, file: BinaryIO, filename: str, content_type: str, bucket: str = "avatars") -> str:
        """Uploads a file and returns its public URL or identifier."""
        pass

    @abstractmethod
    async def delete_file(self, file_url: str, bucket: str = "avatars") -> bool:
        """Deletes a file given its URL or identifier."""
        pass


class LocalStorageProvider(StorageProvider):
    """Local disk storage provider implementation."""

    def __init__(self, base_path: str = "data/storage"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def upload_file(self, file: BinaryIO, filename: str, content_type: str, bucket: str = "avatars") -> str:
        bucket_path = self.base_path / bucket
        bucket_path.mkdir(parents=True, exist_ok=True)

        ext = os.path.splitext(filename)[1]
        unique_filename = f"{uuid.uuid4().hex}{ext}"
        file_path = bucket_path / unique_filename

        with open(file_path, "wb") as f:
            shutil.copyfileobj(file, f)

        # In a real app, this would be a public URL served by the API or Nginx
        # For local dev, we return a path that the API will serve
        return f"/api/v1/storage/{bucket}/{unique_filename}"

    async def delete_file(self, file_url: str, bucket: str = "avatars") -> bool:
        try:
            # Assuming URL is like /api/v1/storage/{bucket}/{filename}
            filename = file_url.split("/")[-1]
            file_path = self.base_path / bucket / filename
            if file_path.exists():
                file_path.unlink()
                return True
        except Exception:
            pass
        return False


# Factory to get the configured provider
def get_storage_provider() -> StorageProvider:
    # Later this can be configured via environment variables
    return LocalStorageProvider()
