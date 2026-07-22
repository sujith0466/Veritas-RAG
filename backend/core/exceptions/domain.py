"""Domain-specific application exceptions.

These cover business-logic error conditions that are not infrastructure failures.
All extend ApplicationException and produce 4xx HTTP responses.
"""

from http import HTTPStatus

from .base import ApplicationException


class ValidationException(ApplicationException):
    """400 — Input failed schema or business-rule validation."""

    error_code = "VAL_001"
    default_message = "Request validation failed"
    http_status = HTTPStatus.BAD_REQUEST


class NotFoundException(ApplicationException):
    """404 — Requested resource does not exist."""

    error_code = "NOT_FOUND_001"
    default_message = "Resource not found"
    http_status = HTTPStatus.NOT_FOUND


class ConflictException(ApplicationException):
    """409 — Request conflicts with the current resource state."""

    error_code = "CONFLICT_001"
    default_message = "Resource conflict"
    http_status = HTTPStatus.CONFLICT


class RateLimitException(ApplicationException):
    """429 — Too many requests; client should back off."""

    error_code = "RATE_001"
    default_message = "Rate limit exceeded. Please slow down your requests."
    http_status = HTTPStatus.TOO_MANY_REQUESTS


class BusinessRuleException(ApplicationException):
    """422 — Request is well-formed but violates a business rule."""

    error_code = "BIZ_001"
    default_message = "Operation violates a business rule"
    http_status = HTTPStatus.UNPROCESSABLE_ENTITY


# ── RAG-specific domain exceptions (reserved for Phase 2+) ─────────────────────


class RetrievalException(ApplicationException):
    """500 — Retrieval pipeline encountered an unrecoverable error."""

    error_code = "RET_001"
    default_message = "Retrieval pipeline error"
    http_status = HTTPStatus.INTERNAL_SERVER_ERROR


class RetryBudgetExhaustedException(BusinessRuleException):
    """422 — Self-correction loop exhausted its retry budget.

    Per BR-1: maximum of two automatic retries per query.
    """

    error_code = "SC_001"
    default_message = "Self-correction retry budget exhausted"


class ConfidenceThresholdException(BusinessRuleException):
    """422 — Retrieved context confidence is below the acceptance threshold."""

    error_code = "SC_002"
    default_message = (
        "Retrieved context does not meet the confidence threshold for generation"
    )


class IngestionException(ApplicationException):
    """400 — Document ingestion failed validation or processing."""

    error_code = "ING_001"
    default_message = "Document ingestion failed"
    http_status = HTTPStatus.BAD_REQUEST
