"""Middleware package for Veritas RAG."""

from .admission_control import (
    AdmissionControlMiddleware,
    acquire_snapshot_barrier_exclusive,
    acquire_snapshot_barrier_shared,
    release_snapshot_barrier_exclusive,
)
from .concurrency import SSEConcurrencyLimiterMiddleware
from .correlation import CorrelationIDMiddleware
from .observability import ObservabilityMiddleware
from .provisioning_guard import WorkspaceProvisioningGuardMiddleware
from .proxy import TrustedProxyMiddleware
from .security_headers import SecurityHeadersMiddleware

__all__ = [
    "AdmissionControlMiddleware",
    "CorrelationIDMiddleware",
    "ObservabilityMiddleware",
    "SecurityHeadersMiddleware",
    "SSEConcurrencyLimiterMiddleware",
    "TrustedProxyMiddleware",
    "WorkspaceProvisioningGuardMiddleware",
    "acquire_snapshot_barrier_exclusive",
    "acquire_snapshot_barrier_shared",
    "release_snapshot_barrier_exclusive",
]
