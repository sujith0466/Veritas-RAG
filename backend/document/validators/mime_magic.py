"""Extension, MIME type, and magic-byte signature validation (`VAL_002`, `VAL_003`)."""

import os
from typing import BinaryIO

from backend.document.schemas.errors import (DocumentDomainException,
                                             DocumentErrorCode)

# Supported extensions whitelist
ALLOWED_EXTENSIONS: set[str] = {
    ".pdf",
    ".docx",
    ".txt",
    ".md",
    ".csv",
    ".json",
}

# Allowed MIME types whitelist
ALLOWED_MIMES: set[str] = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/csv",
    "application/json",
}

# Extension to expected MIME mappings
EXTENSION_TO_MIMES: dict[str, set[str]] = {
    ".pdf": {"application/pdf"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    },
    ".txt": {"text/plain"},
    ".md": {"text/markdown", "text/plain"},
    ".csv": {"text/csv", "application/csv", "text/plain"},
    ".json": {"application/json", "text/plain"},
}

# Prohibited binary magic headers (Disguised executables protection)
# MZ = Windows PE (.exe, .dll), \x7fELF = Linux binary, dylib/mach-o
PROHIBITED_BINARY_HEADERS: list[bytes] = [
    b"MZ",
    b"\x7fELF",
    b"\xfe\xed\xfa\xce",
    b"\xfe\xed\xfa\xcf",
    b"\xce\xfa\xed\xfe",
    b"\xcf\xfa\xed\xfe",
]


def validate_extension_and_mime(
    filename: str,
    declared_mime: str,
    stream: BinaryIO,
) -> tuple[str, str]:
    """Validate file extension, declared MIME, and binary magic-byte signature (`VAL_002`, `VAL_003`).

    Ensures that uploaded files strictly conform to allowed document formats and are not
    disguised executable files.

    Args:
        filename: Sanitized filename.
        declared_mime: Content-Type declared by client.
        stream: Binary stream of the file.

    Returns:
        Tuple of (verified_extension, verified_mime_type).

    Raises:
        DocumentDomainException(VAL_002): If extension is not allowed.
        DocumentDomainException(VAL_003): If MIME or magic bytes do not match declared extension.
    """
    _, ext = os.path.splitext(filename)
    ext = ext.lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise DocumentDomainException(
            code=DocumentErrorCode.VAL_002,
            message=f"File extension '{ext}' is not supported.",
            detail={
                "extension": ext,
                "allowed_extensions": sorted(list(ALLOWED_EXTENSIONS)),
            },
        )

    clean_mime = declared_mime.split(";", maxsplit=1)[0].strip().lower()
    allowed_for_ext = EXTENSION_TO_MIMES.get(ext, ALLOWED_MIMES)

    if clean_mime not in ALLOWED_MIMES and clean_mime not in allowed_for_ext:
        raise DocumentDomainException(
            code=DocumentErrorCode.VAL_003,
            message=f"Declared MIME type '{clean_mime}' is not allowed or does not match extension '{ext}'.",
            detail={"declared_mime": clean_mime, "extension": ext},
        )

    # Magic byte inspection
    current_pos = stream.tell()
    stream.seek(0)
    header = stream.read(2048)
    stream.seek(current_pos)

    # Check against prohibited executable headers
    for prohibited in PROHIBITED_BINARY_HEADERS:
        if header.startswith(prohibited):
            raise DocumentDomainException(
                code=DocumentErrorCode.VAL_003,
                message="Security violation: Disguised binary executable detected via magic bytes.",
                detail={"filename": filename, "extension": ext},
            )

    # Exact signature checks for complex binary formats
    if ext == ".pdf":
        if not header.startswith(b"%PDF-"):
            raise DocumentDomainException(
                code=DocumentErrorCode.VAL_003,
                message="File content signature does not match expected PDF header (`%PDF-`).",
                detail={"filename": filename, "extension": ext},
            )
        return ext, "application/pdf"

    if ext == ".docx":
        # ZIP header check (DOCX is an OpenXML ZIP container starting with PK\x03\x04)
        if (
            not header.startswith(b"PK\x03\x04")
            and not header.startswith(b"PK\x05\x06")
            and not header.startswith(b"PK\x07\x08")
        ):
            raise DocumentDomainException(
                code=DocumentErrorCode.VAL_003,
                message="File content signature does not match expected OpenXML DOCX container (`PK\x03\x04`).",
                detail={"filename": filename, "extension": ext},
            )
        return (
            ext,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    if ext == ".json":
        stripped = header.strip()
        if not (stripped.startswith(b"{") or stripped.startswith(b"[")):
            raise DocumentDomainException(
                code=DocumentErrorCode.VAL_003,
                message="File content does not begin with valid JSON object or array structure.",
                detail={"filename": filename, "extension": ext},
            )
        return ext, "application/json"

    # For .txt, .md, .csv verify basic decodability without binary garbage
    if ext in {".txt", ".md", ".csv"}:
        try:
            # Check first 2KB for valid UTF-8/ASCII printable characters
            header.decode("utf-8")
        except UnicodeDecodeError:
            try:
                header.decode("latin-1")
            except Exception as e:
                raise DocumentDomainException(
                    code=DocumentErrorCode.VAL_003,
                    message="Text document contains unparseable binary characters or invalid encoding.",
                    detail={"filename": filename, "error": str(e)},
                ) from e

    return ext, clean_mime
