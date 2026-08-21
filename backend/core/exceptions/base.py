"""Base exception classes for Veritas RAG.

All custom exceptions extend RAGuardException, which carries:
- A machine-readable error code (e.g., "AUTH_001")
- A human-readable message
- An HTTP status code for API response mapping
- Optional structured detail for debugging

The two-branch hierarchy (Application vs Infrastructure) maps cleanly to
4xx client errors and 5xx server errors respectively.
"""

from http import HTTPStatus
from typing import Any


class RAGuardException(Exception):
    """Root exception for all Veritas RAG application errors.

    Do not raise this directly. Use a specific subclass.
    """

    # Machine-readable code — prefix_NNN pattern (e.g., "AUTH_001")
    error_code: str = "INTERNAL_000"
    default_message: str = "An unexpected error occurred"
    http_status: int = HTTPStatus.INTERNAL_SERVER_ERROR

    def __init__(
        self,
        message: str | None = None,
        detail: dict[str, Any] | None = None,
        error_code: str | None = None,
    ) -> None:
        self.message = message or self.default_message
        self.detail = detail or {}
        if error_code:
            self.error_code = error_code
        super().__init__(self.message)


class ApplicationException(RAGuardException):
    """4xx client-facing errors.

    Indicates a problem with the request, credentials, or client state.
    The client can typically fix these by changing their request.
    """

    http_status: int = HTTPStatus.BAD_REQUEST


class InfrastructureException(RAGuardException):
    """5xx server-side infrastructure errors.

    Indicates a failure in a downstream dependency (database, cache, vector DB,
    external API). The client cannot fix these; they require operator attention.
    """

    http_status: int = HTTPStatus.SERVICE_UNAVAILABLE
