"""Circuit Breaker State Machine Enumerations (`ADR-005`, `Phase 2 Milestone 5`)."""

from enum import Enum


class CircuitState(str, Enum):
    """Represents the health state of a circuit breaker protecting an external service target."""

    CLOSED = "CLOSED"  # Healthy: Traffic flows normally.
    OPEN = "OPEN"  # Tripped: Fast failover to fallback path; traffic blocked.
    HALF_OPEN = "HALF_OPEN"  # Probe: Limited test requests allowed to verify target recovery.
