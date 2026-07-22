from enum import StrEnum

from backend.core.exceptions.base import RAGuardException


class RewriteErrorCode(StrEnum):
    REWRITE_FAILED = "QRW_001"
    DECOMPOSITION_FAILED = "QRW_002"
    CLARIFICATION_GENERATION_FAILED = "QRW_003"


class RewriteDomainException(RAGuardException):
    """Base exception for query rewrite domain."""

    def __init__(self, message: str, error_code: str, detail: dict | None = None):
        super().__init__(message=message, error_code=error_code, detail=detail)


class QueryRewriteFailed(RewriteDomainException):
    def __init__(
        self, message: str = "Failed to rewrite query", detail: dict | None = None
    ):
        super().__init__(
            message=message, error_code=RewriteErrorCode.REWRITE_FAILED, detail=detail
        )


class DecompositionFailed(RewriteDomainException):
    def __init__(
        self, message: str = "Failed to decompose query", detail: dict | None = None
    ):
        super().__init__(
            message=message,
            error_code=RewriteErrorCode.DECOMPOSITION_FAILED,
            detail=detail,
        )


class ClarificationGenerationFailed(RewriteDomainException):
    def __init__(
        self,
        message: str = "Failed to generate clarification questions",
        detail: dict | None = None,
    ):
        super().__init__(
            message=message,
            error_code=RewriteErrorCode.CLARIFICATION_GENERATION_FAILED,
            detail=detail,
        )
