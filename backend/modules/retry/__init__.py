"""
Phase 3 Milestone 3: Deterministic Retry Controller

Provides a state machine to orchestrate the RAGuard query lifecycle, preventing infinite loops.
Limits retries to max 2 and strictly enforces monotonic improvement.
"""
