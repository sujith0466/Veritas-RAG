"""Fallbacks package exports (`ADR-005`, `Phase 2 Milestone 5`)."""

from backend.modules.reliability.fallbacks.router import FallbackRouter
from backend.modules.reliability.fallbacks.zero_result import \
    ZeroResultRecoverer

__all__ = ["FallbackRouter", "ZeroResultRecoverer"]
