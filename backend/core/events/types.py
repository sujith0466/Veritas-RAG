"""Event type enumeration for RAGuard AI.

All internal domain events are registered here. This is the canonical list
of events the system can emit. Handlers are registered per EventType in the
EventDispatcher.

Naming convention: PAST_TENSE_NOUN (e.g., DOCUMENT_UPLOADED, not UPLOAD_DOCUMENT)
"""

from enum import StrEnum


class EventType(StrEnum):
    """All domain events that can be emitted by the RAGuard AI platform."""

    # ── Workspace Lifecycle ────────────────────────────────────────────────────
    WORKSPACE_ARCHIVED = "workspace.archived"
    WORKSPACE_RESTORED = "workspace.restored"
    WORKSPACE_SUSPENDED = "workspace.suspended"
    WORKSPACE_UNSUSPENDED = "workspace.unsuspended"
    WORKSPACE_SOFT_DELETED = "workspace.soft_deleted"
    WORKSPACE_PURGING_STARTED = "workspace.purging_started"
    WORKSPACE_HARD_DELETED = "workspace.hard_deleted"

    # ── Workspace Settings & Branding ──────────────────────────────────────────
    WORKSPACE_SETTINGS_UPDATED = "workspace.settings_updated"
    WORKSPACE_SETTINGS_RESET = "workspace.settings_reset"
    WORKSPACE_SETTINGS_IMPORTED = "workspace.settings_imported"
    WORKSPACE_BRANDING_UPDATED = "workspace.branding_updated"

    # ── Workspace Invitations & Members (Epic 4) ──────────────────────────────
    WORKSPACE_INVITATION_CREATED = "workspace.invitation_created"
    WORKSPACE_INVITATION_RESENT = "workspace.invitation_resent"
    WORKSPACE_INVITATION_REVOKED = "workspace.invitation_revoked"
    WORKSPACE_INVITATION_EXPIRED = "workspace.invitation_expired"
    WORKSPACE_INVITATION_ACCEPTED = "workspace.invitation_accepted"
    WORKSPACE_INVITATION_ACCEPT_FAILED = "workspace.invitation_accept_failed"
    WORKSPACE_MEMBER_ROLE_UPDATED = "workspace.member_role_updated"
    WORKSPACE_MEMBER_SUSPENDED = "workspace.member_suspended"
    WORKSPACE_MEMBER_RESTORED = "workspace.member_restored"
    WORKSPACE_MEMBER_REMOVED = "workspace.member_removed"

    # ── User Profile (Epic 4) ──────────────────────────────────────────────────
    USER_PROFILE_UPDATED = "user.profile_updated"

    # ── Feature Flags ──────────────────────────────────────────────────────────
    FEATURE_FLAG_CREATED = "feature_flag.created"
    FEATURE_FLAG_UPDATED = "feature_flag.updated"
    FEATURE_FLAG_KILLSWITCH_TRIGGERED = "feature_flag.killswitch_triggered"
    FEATURE_FLAG_RULE_UPDATED = "feature_flag.rule_updated"

    # ── Folder Lifecycle (Epic 5) ──────────────────────────────────────────────
    FOLDER_CREATED = "folder.created"
    FOLDER_RENAMED = "folder.renamed"
    FOLDER_SOFT_DELETED = "folder.soft_deleted"
    FOLDER_RESTORED = "folder.restored"
    FOLDER_CHILDREN_SOFT_DELETED = "folder.children_soft_deleted"
    FOLDER_CHILDREN_RESTORED = "folder.children_restored"
    FOLDER_MOVED = "folder.moved"
    FOLDER_SUBTREE_MOVED = "folder.subtree_moved"
    FOLDER_MOVE_FAILED = "folder.move_failed"
    FOLDER_PURGE_STARTED = "folder.purge_started"
    FOLDER_HARD_DELETED = "folder.hard_deleted"
    FOLDER_PURGE_FAILED = "folder.purge_failed"

    # ── Document Lifecycle ─────────────────────────────────────────────────────
    DOCUMENT_UPLOADED = "document.uploaded"
    DOCUMENT_INGESTION_STARTED = "document.ingestion_started"
    DOCUMENT_INGESTION_COMPLETED = "document.ingestion_completed"
    DOCUMENT_INGESTION_FAILED = "document.ingestion_failed"
    DOCUMENT_DELETED = "document.deleted"
    DOCUMENT_ARCHIVED = "document.archived"
    DOCUMENT_RESTORED = "document.restored"
    DOCUMENT_VERSION_CREATED = "document.version_created"
    DOCUMENT_ROLLED_BACK = "document.rolled_back"

    # ── Chunking Pipeline ──────────────────────────────────────────────────────
    CHUNKING_STARTED = "chunking.started"
    CHUNKING_COMPLETED = "chunking.completed"
    CHUNKING_FAILED = "chunking.failed"

    # ── Embedding Pipeline ─────────────────────────────────────────────────────
    EMBEDDING_STARTED = "embedding.started"
    EMBEDDING_PROGRESS = "embedding.progress"
    EMBEDDING_COMPLETED = "embedding.completed"
    EMBEDDING_FAILED = "embedding.failed"

    # ── Vector Storage Foundation ─────────────────────────────────────────────
    VECTORS_INDEXED = "vector.indexed"
    VECTORS_INDEX_FAILED = "vector.index_failed"

    # ── Query Pipeline ─────────────────────────────────────────────────────────
    QUERY_RECEIVED = "query.received"
    QUERY_RETRIEVED = "query.retrieved"
    RETRIEVAL_COMPLETED = "retrieval.completed"
    RETRIEVAL_FAILED = "retrieval.failed"
    CONFIDENCE_EVALUATED = "confidence.evaluated"

    # ── Self-Correction ────────────────────────────────────────────────────────
    RETRY_TRIGGERED = "retry.triggered"
    RETRY_SUCCEEDED = "retry.succeeded"
    RETRY_BUDGET_EXHAUSTED = "retry.budget_exhausted"
    CLARIFICATION_REQUESTED = "clarification.requested"

    # ── Generation & Validation ────────────────────────────────────────────────
    GENERATION_COMPLETED = "generation.completed"
    VALIDATION_COMPLETED = "validation.completed"
    VALIDATION_REJECTED = "validation.rejected"

    # ── Retrieval Reliability (M5) ─────────────────────────────────────────────
    RETRIEVAL_FALLBACK_TRIGGERED = "retrieval.fallback_triggered"
    CIRCUIT_BREAKER_TRIPPED = "retrieval.circuit_breaker_tripped"

    # ── Reflection ─────────────────────────────────────────────────────────────
    REFLECTION_COMPLETED = "reflection.completed"
    REFLECTION_REJECTED = "reflection.rejected"

    # ── Reliability Scoring ────────────────────────────────────────────────────
    RELIABILITY_SCORE_COMPUTED = "reliability_score.computed"

    # ── Evaluation ────────────────────────────────────────────────────────────
    EVALUATION_STARTED = "evaluation.started"
    EVALUATION_COMPLETED = "evaluation.completed"

    # ── Knowledge Health ──────────────────────────────────────────────────────
    KNOWLEDGE_HEALTH_SCAN_STARTED = "knowledge_health.scan_started"
    KNOWLEDGE_HEALTH_SCAN_COMPLETED = "knowledge_health.scan_completed"
    ORPHAN_CHUNKS_PURGED = "knowledge_health.orphans_purged"
    KNOWLEDGE_DRIFT_DETECTED = "knowledge_health.drift_detected"

    # ── System ────────────────────────────────────────────────────────────────
    SYSTEM_STARTUP_COMPLETED = "system.startup_completed"
    SYSTEM_SHUTDOWN_INITIATED = "system.shutdown_initiated"
