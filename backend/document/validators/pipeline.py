"""Orchestrated multi-tier Validation Pipeline (`ValidationPipeline`).

Runs size, sanitization, extension/MIME/magic bytes, virus scanning, and SHA-256 calculation.
"""

from dataclasses import dataclass
from typing import BinaryIO

from backend.document.utils.hashing import calculate_sha256

from .mime_magic import validate_extension_and_mime
from .sanitization import sanitize_filename
from .size import validate_size
from .virus_scan import CleanPassScanner, VirusScanner


@dataclass
class ValidationResult:
    """Structured output of a successful validation run."""

    sanitized_filename: str
    original_filename: str
    file_size_bytes: int
    extension: str
    mime_type: str
    content_hash: str


class ValidationPipeline:
    """Orchestrates sequential multi-layer file validation and security screening."""

    def __init__(self, virus_scanner: VirusScanner | None = None) -> None:
        self.virus_scanner = virus_scanner or CleanPassScanner()

    async def validate(
        self,
        stream: BinaryIO,
        original_filename: str,
        declared_mime: str,
        max_size_bytes: int | None = None,
    ) -> ValidationResult:
        """Execute the full 6-stage validation pipeline on an input file stream.

        Returns:
            ValidationResult containing sanitized filename, size, verified MIME, and SHA-256 hash.
        """
        # 1. Size check (`VAL_001`)
        if max_size_bytes:
            file_size = validate_size(stream, max_bytes=max_size_bytes)
        else:
            file_size = validate_size(stream)

        # 2. Filename sanitization & path traversal defense (`VAL_004`)
        sanitized = sanitize_filename(original_filename)

        # 3. Extension, MIME, and magic byte signature check (`VAL_002`, `VAL_003`)
        ext, verified_mime = validate_extension_and_mime(
            sanitized, declared_mime, stream
        )

        # 4. Virus and malware scan (`VAL_005`)
        await self.virus_scanner.scan(stream, sanitized)

        # 5. SHA-256 stream content hash calculation
        content_hash = calculate_sha256(stream)

        return ValidationResult(
            sanitized_filename=sanitized,
            original_filename=original_filename,
            file_size_bytes=file_size,
            extension=ext,
            mime_type=verified_mime,
            content_hash=content_hash,
        )
