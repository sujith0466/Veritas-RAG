"""Storage Object Entity Model.

Represents physical file artifacts across local or cloud object storage providers.
"""

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import BaseModel


class StorageObject(BaseModel):
    """Physical artifact in object storage."""

    __tablename__ = "storage_objects"

    provider: Mapped[str] = mapped_column(String(50), default="local", nullable=False)
    bucket_or_container: Mapped[str] = mapped_column(String(255), nullable=False)
    object_key: Mapped[str] = mapped_column(String(512), unique=True, index=True, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(128), index=True, nullable=False)

    def __repr__(self) -> str:
        return f"<StorageObject(id={self.id}, provider='{self.provider}', key='{self.object_key}')>"
