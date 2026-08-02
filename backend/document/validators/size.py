"""Document size and quota validators (`VAL_001`)."""

from typing import BinaryIO

from backend.document.schemas.errors import DocumentDomainException, DocumentErrorCode

# Default maximum upload size: 50 MB
DEFAULT_MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024


def validate_size(
    stream: BinaryIO,
    max_bytes: int = DEFAULT_MAX_FILE_SIZE_BYTES,
    tenant_quota_remaining: int | None = None,
) -> int:
    """Validate that the input stream size is within maximum allowed quota (`VAL_001`).

    Args:
        stream: Input binary stream to check.
        max_bytes: Maximum allowed file size in bytes (default 50MB).
        tenant_quota_remaining: Optional remaining quota for the tenant namespace.

    Returns:
        The verified stream length in bytes.

    Raises:
        DocumentDomainException(VAL_001): If file size exceeds limits or quota.
    """
    current_pos = stream.tell()
    stream.seek(0, 2)  # Seek to end
    file_size = stream.tell()
    stream.seek(current_pos)  # Reset to original position

    if file_size == 0:
        raise DocumentDomainException(
            code=DocumentErrorCode.VAL_001,
            message="Uploaded file is empty (0 bytes).",
            detail={"file_size_bytes": 0},
        )

    if file_size > max_bytes:
        raise DocumentDomainException(
            code=DocumentErrorCode.VAL_001,
            message=f"File size ({file_size / (1024 * 1024):.2f} MB) exceeds maximum allowed size ({max_bytes / (1024 * 1024):.2f} MB).",
            detail={"file_size_bytes": file_size, "max_allowed_bytes": max_bytes},
        )

    if tenant_quota_remaining is not None and file_size > tenant_quota_remaining:
        raise DocumentDomainException(
            code=DocumentErrorCode.VAL_001,
            message="File size exceeds remaining tenant storage quota.",
            detail={
                "file_size_bytes": file_size,
                "tenant_quota_remaining": tenant_quota_remaining,
            },
        )

    return file_size
