from datetime import UTC, datetime
from typing import Any
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.entities.audit_log import AuditLog
from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.repositories.workspace import WorkspaceRepository
from backend.repositories.workspace_member import WorkspaceMemberRepository


class WorkspaceConflictError(Exception):
    pass


class WorkspaceNotFoundError(Exception):
    pass


class WorkspaceUnauthorizedError(Exception):
    pass


class WorkspaceInvalidStateError(Exception):
    pass


class WorkspaceManagementService:
    def __init__(
        self,
        workspace_repo: WorkspaceRepository,
        workspace_member_repo: WorkspaceMemberRepository,
    ):
        self.workspace_repo = workspace_repo
        self.workspace_member_repo = workspace_member_repo

    async def update_workspace(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        expected_updated_at: datetime,
        name: str | None = None,
        description: str | None = None,
    ) -> Workspace:
        """Update workspace details with optimistic concurrency."""

        # 1. Check membership and authorization
        member = await self.workspace_member_repo.get_membership(workspace_id, user_id)
        if not member:
            raise WorkspaceNotFoundError("Workspace not found or access denied.")

        if member.role not in ["OWNER", "ADMIN"]:
            raise WorkspaceUnauthorizedError("Only OWNER or ADMIN can update workspace settings.")

        # 2. Get Workspace
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise WorkspaceNotFoundError("Workspace not found.")

        # 3. Check State
        if workspace.status != WorkspaceStatus.ACTIVE.value:
            raise WorkspaceInvalidStateError("Only ACTIVE workspaces can be updated.")

        # 4. Optimistic Concurrency Check
        # Compare replacing tzinfo if necessary, or just exact match
        # SQLAlchemy returns UTC aware datetimes (or naive depending on dialect).
        # We assume both are UTC aware for this comparison.
        if workspace.updated_at.replace(tzinfo=None) != expected_updated_at.replace(tzinfo=None):
            raise WorkspaceConflictError("Workspace has been modified by another user. Please refresh and try again.")

        # 5. Normalize Inputs
        if name is not None:
            name = name.strip()

        # 6. Detect Changes
        changes: dict[str, Any] = {}
        previous_values: dict[str, Any] = {}
        new_values: dict[str, Any] = {}

        if name is not None and name != workspace.name:
            previous_values["name"] = workspace.name
            new_values["name"] = name
            changes["name"] = name

        if description is not None and description != workspace.description:
            previous_values["description"] = workspace.description
            new_values["description"] = description
            changes["description"] = description

        # 7. Skip if no-op
        if not changes:
            return workspace

        # 8. Apply Changes
        if "name" in changes:
            workspace.name = changes["name"]
        if "description" in changes:
            workspace.description = changes["description"]

        session.add(workspace)

        # 9. Audit Log
        audit_log = AuditLog(
            action="WORKSPACE_UPDATED",
            user_id=user_id,
            resource_type="WORKSPACE",
            resource_id=str(workspace_id),
            details={
                "changed_fields": list(changes.keys()),
                "previous_values": previous_values,
                "new_values": new_values
            },
            status="success"
        )
        session.add(audit_log)

        await session.flush()
        await session.commit()
        await session.refresh(workspace)

        return workspace

    async def archive_workspace(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        expected_updated_at: datetime,
        confirmation_name: str,
        reason: str | None = None
    ) -> Workspace:
        """Archive a workspace, pausing all operations while preserving data."""
        # 1. Check membership and authorization
        member = await self.workspace_member_repo.get_membership(workspace_id, user_id)
        if not member:
            raise WorkspaceNotFoundError("Workspace not found or access denied.")

        if member.role not in ["OWNER", "ADMIN"]:
            raise WorkspaceUnauthorizedError("Only OWNER or ADMIN can archive the workspace.")

        # 2. Get Workspace
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise WorkspaceNotFoundError("Workspace not found.")

        # 3. Confirmation check
        if workspace.name != confirmation_name:
            raise ValueError("Confirmation name does not match workspace name.")

        # 4. State validation
        if workspace.status == WorkspaceStatus.ARCHIVED.value:
            raise WorkspaceInvalidStateError("Workspace is already archived.")
        if workspace.status not in [WorkspaceStatus.ACTIVE.value]:
            raise WorkspaceInvalidStateError(f"Cannot archive workspace in {workspace.status} state.")

        # 5. Optimistic Concurrency Check
        if workspace.updated_at.replace(tzinfo=None) != expected_updated_at.replace(tzinfo=None):
            raise WorkspaceConflictError("Workspace has been modified by another user. Please refresh and try again.")

        # 6. Apply Changes
        workspace.status = WorkspaceStatus.ARCHIVED.value
        session.add(workspace)

        # 7. Audit Log
        audit_log = AuditLog(
            action="WORKSPACE_ARCHIVED",
            user_id=user_id,
            resource_type="WORKSPACE",
            resource_id=str(workspace_id),
            details={
                "reason": reason,
                "changed_fields": ["status"],
                "previous_values": {"status": "ACTIVE"},
                "new_values": {"status": "ARCHIVED"}
            },
            status="success"
        )
        session.add(audit_log)

        await session.flush()

        # 8. Dispatch event
        from backend.core.events.dispatcher import get_dispatcher
        from backend.services.workspace.events import WorkspaceArchivedEvent
        dispatcher = get_dispatcher()
        await dispatcher.publish(WorkspaceArchivedEvent(
            workspace_id=str(workspace_id),
            actor_id=str(user_id),
            details={"reason": reason}
        ))

        await session.commit()
        await session.refresh(workspace)
        return workspace

    async def restore_workspace(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        expected_updated_at: datetime
    ) -> Workspace:
        """Restore an archived workspace to ACTIVE state."""
        # 1. Check membership and authorization
        member = await self.workspace_member_repo.get_membership(workspace_id, user_id)
        if not member:
            raise WorkspaceNotFoundError("Workspace not found or access denied.")

        if member.role not in ["OWNER", "ADMIN"]:
            raise WorkspaceUnauthorizedError("Only OWNER or ADMIN can restore the workspace.")

        # 2. Get Workspace
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise WorkspaceNotFoundError("Workspace not found.")

        # 3. State validation
        if workspace.status != WorkspaceStatus.ARCHIVED.value:
            raise WorkspaceInvalidStateError(f"Cannot restore workspace in {workspace.status} state.")

        # 4. Optimistic Concurrency Check
        if workspace.updated_at.replace(tzinfo=None) != expected_updated_at.replace(tzinfo=None):
            raise WorkspaceConflictError("Workspace has been modified by another user. Please refresh and try again.")

        # 5. Apply Changes
        workspace.status = WorkspaceStatus.ACTIVE.value
        session.add(workspace)

        # 6. Audit Log
        audit_log = AuditLog(
            action="WORKSPACE_RESTORED",
            user_id=user_id,
            resource_type="WORKSPACE",
            resource_id=str(workspace_id),
            details={
                "changed_fields": ["status"],
                "previous_values": {"status": "ARCHIVED"},
                "new_values": {"status": "ACTIVE"}
            },
            status="success"
        )
        session.add(audit_log)

        await session.flush()

        # 7. Dispatch event
        from backend.core.events.dispatcher import get_dispatcher
        from backend.services.workspace.events import WorkspaceRestoredEvent
        dispatcher = get_dispatcher()
        await dispatcher.publish(WorkspaceRestoredEvent(
            workspace_id=str(workspace_id),
            actor_id=str(user_id)
        ))

        await session.commit()
        await session.refresh(workspace)
        return workspace

    async def suspend_workspace(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        admin_id: uuid.UUID,
        admin_email: str,
        expected_updated_at: datetime,
        confirmation_name: str,
        reason_code: str,
        reason_text: str | None = None
    ) -> Workspace:
        """Suspend a workspace by Platform Admin."""
        # 1. Get Workspace
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise WorkspaceNotFoundError("Workspace not found.")

        # 2. Confirmation check
        if workspace.name != confirmation_name:
            raise ValueError("Confirmation name does not match workspace name.")

        # 3. State validation (Idempotency & Legal transitions)
        if workspace.status == WorkspaceStatus.SUSPENDED.value:
            raise WorkspaceConflictError("Workspace is already suspended.")
        if workspace.status != WorkspaceStatus.ACTIVE.value:
            raise WorkspaceInvalidStateError(f"Cannot suspend workspace in {workspace.status} state.")

        # 4. Optimistic Concurrency Check
        if workspace.updated_at.replace(tzinfo=None) != expected_updated_at.replace(tzinfo=None):
            raise WorkspaceConflictError("Workspace has been modified by another administrator. Please refresh and try again.")

        # 5. Apply Changes
        now = datetime.now(UTC)
        workspace.status = WorkspaceStatus.SUSPENDED.value
        workspace.suspended_at = now
        session.add(workspace)

        # 6. Audit Log with rich metadata
        audit_log = AuditLog(
            action="WORKSPACE_SUSPENDED",
            user_id=admin_id,
            resource_type="WORKSPACE",
            resource_id=str(workspace_id),
            details={
                "suspended_by": admin_email,
                "suspended_at": now.isoformat(),
                "reason_code": reason_code,
                "reason_text": reason_text,
                "changed_fields": ["status", "suspended_at"],
                "previous_values": {"status": "ACTIVE", "suspended_at": None},
                "new_values": {"status": "SUSPENDED", "suspended_at": now.isoformat()}
            },
            status="success"
        )
        session.add(audit_log)

        await session.flush()
        await session.commit()
        await session.refresh(workspace)

        # 7. Post-commit event dispatch
        from backend.core.events.dispatcher import get_dispatcher
        from backend.services.workspace.events import WorkspaceSuspendedEvent
        dispatcher = get_dispatcher()
        await dispatcher.publish(WorkspaceSuspendedEvent(
            workspace_id=str(workspace_id),
            actor_id=str(admin_id),
            reason_code=reason_code,
            reason_text=reason_text,
            details={"admin_email": admin_email}
        ))

        return workspace

    async def unsuspend_workspace(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        admin_id: uuid.UUID,
        admin_email: str,
        expected_updated_at: datetime,
        reason_text: str | None = None
    ) -> Workspace:
        """Unsuspend a workspace by Platform Admin."""
        # 1. Get Workspace
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise WorkspaceNotFoundError("Workspace not found.")

        # 2. State validation (Idempotency & Legal transitions)
        if workspace.status == WorkspaceStatus.ACTIVE.value:
            raise WorkspaceConflictError("Workspace is not suspended (current status: ACTIVE).")
        if workspace.status != WorkspaceStatus.SUSPENDED.value:
            raise WorkspaceInvalidStateError(f"Cannot unsuspend workspace in {workspace.status} state.")

        # 3. Optimistic Concurrency Check
        if workspace.updated_at.replace(tzinfo=None) != expected_updated_at.replace(tzinfo=None):
            raise WorkspaceConflictError("Workspace has been modified by another administrator. Please refresh and try again.")

        # 4. Apply Changes
        prev_suspended_at = workspace.suspended_at.isoformat() if workspace.suspended_at else None
        now = datetime.now(UTC)
        workspace.status = WorkspaceStatus.ACTIVE.value
        workspace.suspended_at = None
        session.add(workspace)

        # 5. Audit Log with rich metadata
        audit_log = AuditLog(
            action="WORKSPACE_UNSUSPENDED",
            user_id=admin_id,
            resource_type="WORKSPACE",
            resource_id=str(workspace_id),
            details={
                "unsuspended_by": admin_email,
                "unsuspended_at": now.isoformat(),
                "reason_text": reason_text,
                "changed_fields": ["status", "suspended_at"],
                "previous_values": {"status": "SUSPENDED", "suspended_at": prev_suspended_at},
                "new_values": {"status": "ACTIVE", "suspended_at": None}
            },
            status="success"
        )
        session.add(audit_log)

        await session.flush()
        await session.commit()
        await session.refresh(workspace)

        # 6. Post-commit event dispatch
        from backend.core.events.dispatcher import get_dispatcher
        from backend.services.workspace.events import WorkspaceUnsuspendedEvent
        dispatcher = get_dispatcher()
        await dispatcher.publish(WorkspaceUnsuspendedEvent(
            workspace_id=str(workspace_id),
            actor_id=str(admin_id),
            reason_text=reason_text,
            details={"admin_email": admin_email}
        ))

        return workspace

    async def soft_delete_workspace(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        expected_updated_at: datetime,
        confirmation_name: str,
        reason_code: str,
        reason_text: str | None = None,
        is_platform_admin: bool = False,
    ) -> Workspace:
        """Soft delete a workspace, entering a 30-day retention grace period."""
        # 1. Check authorization (Owner or Platform Admin)
        if not is_platform_admin:
            member = await self.workspace_member_repo.get_membership(workspace_id, user_id)
            if not member:
                raise WorkspaceNotFoundError("Workspace not found or access denied.")
            if member.role != "OWNER":
                raise WorkspaceUnauthorizedError("Only the workspace OWNER or Platform Admin can soft delete a workspace.")

        # 2. Get Workspace
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise WorkspaceNotFoundError("Workspace not found.")

        # 3. Confirmation name check
        if workspace.name != confirmation_name:
            raise ValueError("Confirmation name does not match workspace name.")

        # 4. State validation
        if workspace.status == WorkspaceStatus.DELETING.value:
            raise WorkspaceConflictError("Workspace is already in DELETING status.")
        if workspace.status in [WorkspaceStatus.PURGING.value, WorkspaceStatus.DELETED.value]:
            raise WorkspaceInvalidStateError(f"Cannot soft delete workspace in {workspace.status} state.")

        # 5. Optimistic Concurrency Check
        if workspace.updated_at.replace(tzinfo=None) != expected_updated_at.replace(tzinfo=None):
            raise WorkspaceConflictError("Workspace has been modified by another user. Please refresh and try again.")

        # 6. Apply Changes
        from datetime import timedelta
        now = datetime.now(UTC)
        purge_at = now + timedelta(days=30)
        prev_status = workspace.status

        workspace.status = WorkspaceStatus.DELETING.value
        workspace.deleted_at = now
        workspace.purge_at = purge_at
        workspace.deleted_by_user_id = user_id
        workspace.deletion_reason_code = reason_code
        workspace.deletion_reason_text = reason_text
        session.add(workspace)

        # 7. Audit Log
        audit_log = AuditLog(
            action="WORKSPACE_SOFT_DELETED",
            user_id=user_id,
            resource_type="WORKSPACE",
            resource_id=str(workspace_id),
            details={
                "reason_code": reason_code,
                "reason_text": reason_text,
                "deleted_at": now.isoformat(),
                "purge_at": purge_at.isoformat(),
                "grace_period_days": 30,
                "changed_fields": ["status", "deleted_at", "purge_at", "deleted_by_user_id", "deletion_reason_code", "deletion_reason_text"],
                "previous_values": {"status": prev_status},
                "new_values": {"status": "DELETING", "purge_at": purge_at.isoformat()}
            },
            status="success"
        )
        session.add(audit_log)

        await session.flush()
        await session.commit()
        await session.refresh(workspace)

        # 8. Post-commit event dispatch & metric
        from backend.core.events.dispatcher import get_dispatcher
        from backend.observability.metrics.prometheus import record_workspace_soft_deleted
        from backend.services.workspace.events import WorkspaceSoftDeletedEvent

        record_workspace_soft_deleted()
        dispatcher = get_dispatcher()
        await dispatcher.publish(WorkspaceSoftDeletedEvent(
            workspace_id=str(workspace_id),
            actor_id=str(user_id),
            reason_code=reason_code,
            reason_text=reason_text,
            details={"purge_at": purge_at.isoformat()}
        ))

        return workspace

    async def restore_deleted_workspace(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        expected_updated_at: datetime,
        is_platform_admin: bool = False,
    ) -> Workspace:
        """Restore a soft-deleted workspace within the 30-day grace period."""
        # 1. Check authorization (Owner or Platform Admin only)
        if not is_platform_admin:
            member = await self.workspace_member_repo.get_membership(workspace_id, user_id)
            if not member:
                raise WorkspaceNotFoundError("Workspace not found or access denied.")
            if member.role != "OWNER":
                raise WorkspaceUnauthorizedError("Only the workspace OWNER or Platform Admin can restore a deleted workspace.")

        # 2. Get Workspace
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise WorkspaceNotFoundError("Workspace not found.")

        # 3. State validation
        if workspace.status == WorkspaceStatus.ACTIVE.value:
            raise WorkspaceConflictError("Workspace is already active.")
        if workspace.status != WorkspaceStatus.DELETING.value:
            raise WorkspaceInvalidStateError(f"Cannot restore workspace in {workspace.status} state.")

        # 4. Retention expiration check
        now = datetime.now(UTC)
        if workspace.purge_at and workspace.purge_at < now:
            raise WorkspaceInvalidStateError("The 30-day retention window for this workspace has expired and cannot be restored.")

        # 5. Optimistic Concurrency Check
        if workspace.updated_at.replace(tzinfo=None) != expected_updated_at.replace(tzinfo=None):
            raise WorkspaceConflictError("Workspace has been modified by another user. Please refresh and try again.")

        # 6. Apply Changes
        workspace.status = WorkspaceStatus.ACTIVE.value
        workspace.deleted_at = None
        workspace.purge_at = None
        workspace.deleted_by_user_id = None
        workspace.deletion_reason_code = None
        workspace.deletion_reason_text = None
        session.add(workspace)

        # 7. Audit Log
        audit_log = AuditLog(
            action="WORKSPACE_RESTORED",
            user_id=user_id,
            resource_type="WORKSPACE",
            resource_id=str(workspace_id),
            details={
                "restored_from": "DELETING",
                "changed_fields": ["status", "deleted_at", "purge_at", "deleted_by_user_id", "deletion_reason_code", "deletion_reason_text"],
                "previous_values": {"status": "DELETING"},
                "new_values": {"status": "ACTIVE"}
            },
            status="success"
        )
        session.add(audit_log)

        await session.flush()
        await session.commit()
        await session.refresh(workspace)

        # 8. Post-commit event dispatch & metric
        from backend.core.events.dispatcher import get_dispatcher
        from backend.observability.metrics.prometheus import record_workspace_restored
        from backend.services.workspace.events import WorkspaceRestoredEvent

        record_workspace_restored()
        dispatcher = get_dispatcher()
        await dispatcher.publish(WorkspaceRestoredEvent(
            workspace_id=str(workspace_id),
            actor_id=str(user_id),
            details={"restored_from": "DELETING"}
        ))

        return workspace

    async def hard_delete_workspace(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        admin_id: uuid.UUID,
        confirmation_slug: str,
        reason: str,
        force_immediate: bool = False,
    ) -> dict[str, Any]:
        """Permanently purge a workspace and its external resources (Platform Admin only)."""
        # 1. Get Workspace
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise WorkspaceNotFoundError("Workspace not found.")

        # 2. Slug Confirmation Check
        if workspace.slug != confirmation_slug:
            raise ValueError(f"Confirmation slug '{confirmation_slug}' does not match workspace slug '{workspace.slug}'.")

        # 3. State validation
        if not force_immediate and workspace.status != WorkspaceStatus.DELETING.value:
            raise WorkspaceInvalidStateError("Workspace must be in DELETING state prior to hard delete unless force_immediate is set.")

        # 4. Transition to PURGING
        workspace.status = WorkspaceStatus.PURGING.value
        session.add(workspace)
        await session.flush()
        await session.commit()

        # 5. External Resource Purge
        storage_prefix = workspace.storage_prefix
        qdrant_namespace = workspace.qdrant_namespace

        cleanup_metrics = {
            "workspace_id": str(workspace_id),
            "storage_prefix": storage_prefix,
            "qdrant_namespace": qdrant_namespace,
            "status": "PURGED",
        }

        # Step 5a: S3 object cleanup (idempotent best-effort)
        try:
            from backend.document.storage.cloud import get_storage_client
            storage_client = get_storage_client()
            if hasattr(storage_client, "delete_prefix"):
                await storage_client.delete_prefix(storage_prefix)
        except Exception:
            from backend.observability.metrics.prometheus import record_workspace_cleanup_failure
            record_workspace_cleanup_failure(stage="s3")

        # Step 5b: Qdrant vectors cleanup (idempotent best-effort)
        try:
            from backend.vector_db.client import get_qdrant_client
            qdrant = get_qdrant_client()
            if hasattr(qdrant, "delete_collection"):
                await qdrant.delete_collection(qdrant_namespace)
        except Exception:
            from backend.observability.metrics.prometheus import record_workspace_cleanup_failure
            record_workspace_cleanup_failure(stage="qdrant")

        # Step 5c: Redis cache cleanup
        try:
            from backend.cache.client import get_redis_client
            redis = get_redis_client()
            if hasattr(redis, "delete_pattern"):
                await redis.delete_pattern(f"workspace:{workspace_id}:*")
        except Exception:
            from backend.observability.metrics.prometheus import record_workspace_cleanup_failure
            record_workspace_cleanup_failure(stage="redis")

        # 6. Database Cascade Purge (Note: Audit Logs and Security Logs are permanently preserved!)
        await self.workspace_repo.delete(workspace_id)

        # 7. Permanent Audit Record
        audit_log = AuditLog(
            action="WORKSPACE_HARD_DELETED",
            user_id=admin_id,
            resource_type="WORKSPACE",
            resource_id=str(workspace_id),
            details={
                "reason": reason,
                "force_immediate": force_immediate,
                "cleanup_metrics": cleanup_metrics,
            },
            status="success"
        )
        session.add(audit_log)
        await session.flush()
        await session.commit()

        # 8. Post-commit event & metric
        from backend.core.events.dispatcher import get_dispatcher
        from backend.observability.metrics.prometheus import record_workspace_hard_deleted
        from backend.services.workspace.events import WorkspaceHardDeletedEvent

        record_workspace_hard_deleted()
        dispatcher = get_dispatcher()
        await dispatcher.publish(WorkspaceHardDeletedEvent(
            workspace_id=str(workspace_id),
            actor_id=str(admin_id),
            details=cleanup_metrics
        ))

        return cleanup_metrics


