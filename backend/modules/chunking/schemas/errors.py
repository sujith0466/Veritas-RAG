"""Chunking domain error taxonomy and exception models.

Provides standardized error classifications across strategy resolution, splitting,
validation, contract checking, and repository operations with strict severity
distinction (RECOVERABLE vs FATAL) to drive Celery retry policy.
"""

from enum import StrEnum
from http import HTTPStatus
from typing import Any

from backend.core.exceptions.base import RAGuardException


class ErrorSeverity(StrEnum):
    """Severity level determining background worker retry behavior."""

    RECOVERABLE = "RECOVERABLE"  # Transient database/lock issue; trigger exponential backoff retry
    FATAL = "FATAL"  # Permanent validation/parsing issue; transition immediately to CHUNKING_FAILED


class ChunkErrorCode(StrEnum):
    """Chunking domain error taxonomy."""

    CHK_001 = "CHK_001"  # Chunk validation error (e.g. exceeds quota or empty) — FATAL
    CHK_002 = "CHK_002"  # Chunk strategy unsupported or placeholder invoked — FATAL
    CHK_003 = "CHK_003"  # Execution error during text splitting or AST parsing — FATAL
    CHK_004 = (
        "CHK_004"  # Chunk contract violation (no chunks or broken links) — RECOVERABLE
    )
    CHK_005 = (
        "CHK_005"  # Chunk or document entity not found in repository — RECOVERABLE
    )


ERROR_SEVERITY_MAP: dict[ChunkErrorCode | str, ErrorSeverity] = {
    ChunkErrorCode.CHK_001: ErrorSeverity.FATAL,
    ChunkErrorCode.CHK_002: ErrorSeverity.FATAL,
    ChunkErrorCode.CHK_003: ErrorSeverity.FATAL,
    ChunkErrorCode.CHK_004: ErrorSeverity.RECOVERABLE,
    ChunkErrorCode.CHK_005: ErrorSeverity.RECOVERABLE,
}


def get_error_severity(code: ChunkErrorCode | str) -> ErrorSeverity:
    """Resolve the error severity for a given code. Defaults to RECOVERABLE if unknown."""
    return ERROR_SEVERITY_MAP.get(code, ErrorSeverity.RECOVERABLE)


class ChunkDomainException(RAGuardException):
    """Domain exception raised across Chunking & Document Processing subsystems (`ADR-005`)."""

    def __init__(
        self,
        code: ChunkErrorCode | str,
        message: str,
        detail: dict[str, Any] | None = None,
        severity: ErrorSeverity | None = None,
    ) -> None:
        code_str = (
            code
            if isinstance(code, ChunkErrorCode)
            else (
                ChunkErrorCode(code)
                if code in ChunkErrorCode._value2member_map_
                else str(code)
            )
        )
        self.code = code_str
        self.severity = severity or get_error_severity(self.code)

        status_code = HTTPStatus.INTERNAL_SERVER_ERROR
        if str(code_str) in {"CHK_001", "CHK_002"}:
            status_code = HTTPStatus.BAD_REQUEST
        elif str(code_str) == "CHK_005":
            status_code = HTTPStatus.NOT_FOUND
        elif str(code_str) == "CHK_004":
            status_code = HTTPStatus.UNPROCESSABLE_ENTITY

        self.http_status = int(status_code)
        super().__init__(message=message, detail=detail, error_code=str(code_str))


class ChunkValidationError(ChunkDomainException):
    """Raised when a chunk violates size boundaries or hash invariants (`CHK_001`)."""

    def __init__(self, message: str, detail: dict[str, Any] | None = None) -> None:
        super().__init__(code=ChunkErrorCode.CHK_001, message=message, detail=detail)


class ChunkStrategyNotFound(ChunkDomainException):
    """Raised when a requested strategy is not supported or M2 placeholder is invoked (`CHK_002`)."""

    def __init__(self, message: str, detail: dict[str, Any] | None = None) -> None:
        super().__init__(code=ChunkErrorCode.CHK_002, message=message, detail=detail)


class ChunkingExecutionError(ChunkDomainException):
    """Raised when text splitting encounters an unexpected parsing crash (`CHK_003`)."""

    def __init__(self, message: str, detail: dict[str, Any] | None = None) -> None:
        super().__init__(code=ChunkErrorCode.CHK_003, message=message, detail=detail)


class ChunkContractViolationError(ChunkDomainException):
    """Raised when chunk processing invariant verification fails (`CHK_004`)."""

    def __init__(self, message: str, detail: dict[str, Any] | None = None) -> None:
        super().__init__(code=ChunkErrorCode.CHK_004, message=message, detail=detail)


class ChunkNotFoundException(ChunkDomainException):
    """Raised when a requested chunk or document is missing from the repository (`CHK_005`)."""

    def __init__(self, message: str, detail: dict[str, Any] | None = None) -> None:
        super().__init__(code=ChunkErrorCode.CHK_005, message=message, detail=detail)
