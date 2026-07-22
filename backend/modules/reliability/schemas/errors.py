"""Reliability Module Error Taxonomy (`ADR-005`, `REL_001` to `REL_005`).

Defines structured exceptions for circuit breakers, SLA breaches, and fallback routes.
"""

from http import HTTPStatus
from typing import Any

from backend.core.exceptions import RAGuardException


class ReliabilityDomainException(RAGuardException):
    """Base exception for all Retrieval Reliability module failures."""

    def __init__(
        self,
        code: str,
        message: str,
        is_recoverable: bool = True,
        detail: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.is_recoverable = is_recoverable
        status_code = HTTPStatus.INTERNAL_SERVER_ERROR
        if code == "REL_001":
            status_code = HTTPStatus.BAD_REQUEST
        elif code in {"REL_002", "REL_003", "REL_004"}:
            status_code = HTTPStatus.SERVICE_UNAVAILABLE
        elif code == "REL_005":
            status_code = HTTPStatus.NOT_FOUND

        self.http_status = int(status_code)
        super().__init__(
            message=message,
            detail=detail or {},
            error_code=code,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize exception to standard API error response structure."""
        return {
            "success": False,
            "error": {
                "code": self.code,
                "message": self.message,
                "detail": self.detail,
            },
        }


class CircuitBreakerOpenError(ReliabilityDomainException):
    """REL_001: Raised when a target service circuit breaker is OPEN (tripped)."""

    def __init__(
        self, tenant_id: str, target: str, detail: dict[str, Any] | None = None
    ) -> None:
        super().__init__(
            code="REL_001",
            message=f"Circuit breaker is OPEN for target '{target}' and tenant '{tenant_id}'. Delegating to fallback path.",
            is_recoverable=True,
            detail={"tenant_id": tenant_id, "target": target, **(detail or {})},
        )


class RetrievalSLABreachedError(ReliabilityDomainException):
    """REL_002: Raised when retrieval latency exceeds SLA budget (e.g., > 400ms)."""

    def __init__(
        self,
        tenant_id: str,
        duration_ms: float,
        threshold_ms: float = 400.0,
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="REL_002",
            message=f"Retrieval latency ({duration_ms:.2f}ms) breached SLA budget of {threshold_ms:.2f}ms for tenant '{tenant_id}'.",
            is_recoverable=True,
            detail={
                "tenant_id": tenant_id,
                "duration_ms": duration_ms,
                "threshold_ms": threshold_ms,
                **(detail or {}),
            },
        )


class FailureThresholdExceededError(ReliabilityDomainException):
    """REL_003: Raised when consecutive failures exceed sliding window threshold."""

    def __init__(
        self,
        tenant_id: str,
        target: str,
        failures: int,
        threshold: int = 5,
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="REL_003",
            message=f"Target '{target}' failure count ({failures}) exceeded threshold ({threshold}) for tenant '{tenant_id}'. Tripping circuit.",
            is_recoverable=True,
            detail={
                "tenant_id": tenant_id,
                "target": target,
                "failures": failures,
                "threshold": threshold,
                **(detail or {}),
            },
        )


class FallbackProviderUnavailableError(ReliabilityDomainException):
    """REL_004: Raised when fallback path (e.g., BM25 sparse search) fails or is unavailable."""

    def __init__(
        self, tenant_id: str, reason: str, detail: dict[str, Any] | None = None
    ) -> None:
        super().__init__(
            code="REL_004",
            message=f"Degraded fallback provider is unavailable for tenant '{tenant_id}': {reason}",
            is_recoverable=False,
            detail={"tenant_id": tenant_id, "reason": reason, **(detail or {})},
        )


class ZeroResultRecoveryFailedError(ReliabilityDomainException):
    """REL_005: Raised when zero-result recovery algorithms cannot surface any candidates."""

    def __init__(
        self, tenant_id: str, query: str, detail: dict[str, Any] | None = None
    ) -> None:
        super().__init__(
            code="REL_005",
            message=f"Zero-result recovery failed to surface candidates for tenant '{tenant_id}' query: {query}",
            is_recoverable=False,
            detail={"tenant_id": tenant_id, "query": query, **(detail or {})},
        )


class SelfHealingPolicyError(RAGuardException):
    def __init__(self, message: str):
        super().__init__(message=message, error_code="REL_GOV_001")


class RotationFailedError(RAGuardException):
    def __init__(self, message: str):
        super().__init__(message=message, error_code="REL_GOV_002")
