"""Filename sanitization and path traversal defense (`VAL_004`)."""

import os
import re

from backend.document.schemas.errors import DocumentDomainException, DocumentErrorCode

# Characters prohibited in clean basenames
ILLEGAL_FILENAME_CHARS = re.compile(r'[\x00-\x1f\x7f/\?\\:\*"<>\|]')
PATH_TRAVERSAL_PATTERN = re.compile(r"(\.\./|\.\.\\|\.\.$)")


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """Sanitize filename to prevent path traversal and filesystem vulnerability (`VAL_004`).

    Strips path traversal sequences, null bytes, special characters, and truncates
    to safe length while preserving valid extension.

    Args:
        filename: Raw user-provided filename.
        max_length: Maximum allowed string length (default 255).

    Returns:
        Sanitized, safe basename string.

    Raises:
        DocumentDomainException(VAL_004): If filename is empty or cannot be safely sanitized.
    """
    if not filename or not isinstance(filename, str):
        raise DocumentDomainException(
            code=DocumentErrorCode.VAL_004,
            message="Filename must be a non-empty string.",
        )

    # 1. Strip path components (get pure basename)
    basename = os.path.basename(filename.replace("\\", "/"))

    # 2. Check for explicit path traversal patterns
    if PATH_TRAVERSAL_PATTERN.search(filename) or ".." in basename:
        raise DocumentDomainException(
            code=DocumentErrorCode.VAL_004,
            message="Filename contains illegal path traversal sequences.",
            detail={"original_filename": filename},
        )

    # 3. Strip control bytes and prohibited filesystem symbols
    clean_name = ILLEGAL_FILENAME_CHARS.sub("_", basename).strip()

    # 4. Strip leading dots or whitespace
    clean_name = clean_name.lstrip(". ").rstrip(" ")

    if not clean_name:
        raise DocumentDomainException(
            code=DocumentErrorCode.VAL_004,
            message="Filename became empty after security sanitization.",
            detail={"original_filename": filename},
        )

    # 5. Enforce length truncation while preserving extension
    if len(clean_name) > max_length:
        base, ext = os.path.splitext(clean_name)
        allowed_base_len = max_length - len(ext)
        if allowed_base_len <= 0:
            raise DocumentDomainException(
                code=DocumentErrorCode.VAL_004,
                message="Filename extension is excessively long.",
                detail={"original_filename": filename},
            )
        clean_name = base[:allowed_base_len] + ext

    return clean_name
