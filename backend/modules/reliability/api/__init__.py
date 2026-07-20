"""API package exports (`ADR-005`, `Phase 2 Milestone 5`)."""

from backend.modules.reliability.api.routes import router as reliability_router

__all__ = ["reliability_router"]
