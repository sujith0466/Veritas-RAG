"""Document domain error taxonomy and exception models.

Provides standardized error classifications across validation, storage, extraction, OCR,
system orchestration, and processing contract verification, with strict severity
distinction (RECOVERABLE vs FATAL) to drive Celery retry policy.
"""

from enum import StrEnum
from typing import Any


class ErrorSeverity(StrEnum):
    """Severity level determining background worker retry behavior."""

    RECOVERABLE = "RECOVERABLE"  # Transient issue; trigger exponential backoff retry
    FATAL = "FATAL"              # Permanent issue; immediately transition status to FAILED


class DocumentErrorCode(StrEnum):
    """Document processing error code taxonomy."""

    # Validation errors (VAL_xxx) — FATAL by default
    VAL_001 = "VAL_001"  # File size exceeds allowed quota
    VAL_002 = "VAL_002"  # Disallowed file extension
    VAL_003 = "VAL_003"  # Disallowed or mismatched MIME / magic bytes
    VAL_004 = "VAL_004"  # Filename sanitization failed or path traversal detected
    VAL_005 = "VAL_005"  # Virus detected during validation scan
    VAL_006 = "VAL_006"  # Duplicate document content detected within tenant

    # Storage errors (STORE_xxx) — RECOVERABLE by default
    STORE_001 = "STORE_001"  # Object storage write operation failed
    STORE_002 = "STORE_002"  # Storage object not found or read failure
    STORE_003 = "STORE_003"  # Storage provider connection or quota failure

    # Extraction errors (EXTRACT_xxx)
    EXTRACT_001 = "EXTRACT_001"  # Extractor parsing exception or corrupted structure (FATAL)
    EXTRACT_002 = "EXTRACT_002"  # Minimal text extracted; requires OCR fallback (RECOVERABLE)
    EXTRACT_003 = "EXTRACT_003"  # No capable extractor registered for MIME type (FATAL)

    # OCR errors (OCR_xxx) — RECOVERABLE by default
    OCR_001 = "OCR_001"  # OCR processing engine failure
    OCR_002 = "OCR_002"  # OCR service currently unavailable

    # System & Orchestration errors (SYS_xxx) — RECOVERABLE by default
    SYS_001 = "SYS_001"  # Database or transaction error during pipeline execution
    SYS_002 = "SYS_002"  # Celery task execution failure or worker lost

    # Contract errors (CONTRACT_xxx) — RECOVERABLE by default
    CONTRACT_001 = "CONTRACT_001"  # Document Processing Contract verification failed missing entities/artifacts


ERROR_SEVERITY_MAP: dict[DocumentErrorCode | str, ErrorSeverity] = {
    DocumentErrorCode.VAL_001: ErrorSeverity.FATAL,
    DocumentErrorCode.VAL_002: ErrorSeverity.FATAL,
    DocumentErrorCode.VAL_003: ErrorSeverity.FATAL,
    DocumentErrorCode.VAL_004: ErrorSeverity.FATAL,
    DocumentErrorCode.VAL_005: ErrorSeverity.FATAL,
    DocumentErrorCode.VAL_006: ErrorSeverity.FATAL,
    DocumentErrorCode.STORE_001: ErrorSeverity.RECOVERABLE,
    DocumentErrorCode.STORE_002: ErrorSeverity.RECOVERABLE,
    DocumentErrorCode.STORE_003: ErrorSeverity.RECOVERABLE,
    DocumentErrorCode.EXTRACT_001: ErrorSeverity.FATAL,
    DocumentErrorCode.EXTRACT_002: ErrorSeverity.RECOVERABLE,
    DocumentErrorCode.EXTRACT_003: ErrorSeverity.FATAL,
    DocumentErrorCode.OCR_001: ErrorSeverity.RECOVERABLE,
    DocumentErrorCode.OCR_002: ErrorSeverity.RECOVERABLE,
    DocumentErrorCode.SYS_001: ErrorSeverity.RECOVERABLE,
    DocumentErrorCode.SYS_002: ErrorSeverity.RECOVERABLE,
    DocumentErrorCode.CONTRACT_001: ErrorSeverity.RECOVERABLE,
}


def get_error_severity(code: DocumentErrorCode | str) -> ErrorSeverity:
    """Resolve the error severity for a given code. Defaults to RECOVERABLE if unknown."""
    if isinstance(code, DocumentErrorCode):
        return ERROR_SEVERITY_MAP.get(code, ErrorSeverity.RECOVERABLE)
    return ERROR_SEVERITY_MAP.get(code, ErrorSeverity.RECOVERABLE)


from http import HTTPStatus
from backend.core.exceptions.base import RAGuardException


class DocumentDomainException(RAGuardException):
    """Domain exception raised across Document Intelligence subsystems (`ADR-005`)."""

    def __init__(
        self,
        code: DocumentErrorCode | str,
        message: str,
        detail: dict[str, Any] | None = None,
        severity: ErrorSeverity | None = None,
    ) -> None:
        code_str = code if isinstance(code, DocumentErrorCode) else DocumentErrorCode(code) if code in DocumentErrorCode._value2member_map_ else str(code)
        self.code = code_str
        self.severity = severity or get_error_severity(self.code)

        # Map to HTTP status
        status_code = HTTPStatus.INTERNAL_SERVER_ERROR
        if str(code_str).startswith("VAL_"):
            status_code = HTTPStatus.BAD_REQUEST
        elif str(code_str) == "STORE_002":
            status_code = HTTPStatus.NOT_FOUND
        elif str(code_str).startswith("STORE_"):
            status_code = HTTPStatus.SERVICE_UNAVAILABLE

        self.http_status = int(status_code)
        super().__init__(message=message, detail=detail, error_code=str(code_str))

