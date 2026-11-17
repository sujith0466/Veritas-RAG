import inspect
import re
import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.entities.audit_log import AuditLog
from backend.models.entities.user import User
from backend.models.entities.workspace import ProvisioningStatus, Workspace, WorkspaceStatus
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember, WorkspaceRole
from backend.models.entities.workspace_settings import WorkspaceSettings
from backend.repositories.workspace import WorkspaceRepository
from backend.repositories.workspace_member import WorkspaceMemberRepository
from backend.repositories.workspace_settings import WorkspaceSettingsRepository
from backend.services.workspace.identity import WorkspaceIdGenerator


class WorkspaceProvisioningService:
    def __init__(
        self,
        workspace_repo: WorkspaceRepository,
        workspace_settings_repo: WorkspaceSettingsRepository,
        workspace_member_repo: WorkspaceMemberRepository,
    ):
        self.workspace_repo = workspace_repo
        self.workspace_settings_repo = workspace_settings_repo
        self.workspace_member_repo = workspace_member_repo

    async def _generate_slug(self, name: str) -> str:
        # Base slug generation
        base_slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        if not base_slug:
            base_slug = "workspace"

        slug = base_slug
        collision = await self.workspace_repo.exists_by_slug(slug)

        # In case of collision, append random short suffix
        while collision:
            suffix = secrets.token_hex(2)
            slug = f"{base_slug}-{suffix}"
            collision = await self.workspace_repo.exists_by_slug(slug)

        return slug

    async def provision_workspace(
        self,
        session: AsyncSession,
        name: str,
        description: str | None = None,
        owner_user_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
    ) -> Workspace:
        """Provisions a new workspace with all associated resources."""
        effective_owner_id = owner_user_id or user_id
        if not effective_owner_id:
            raise ValueError("Either owner_user_id or user_id must be provided")

        # 0. Acquire exclusive row lock on target owner user and revalidate active lifecycle state (WP-T3C-5 / R6-F02)
        user_stmt = select(User).where(User.id == effective_owner_id).with_for_update()
        exec_res = await session.execute(user_stmt)
        if hasattr(exec_res, "scalar_one_or_none"):
            target_user = exec_res.scalar_one_or_none()
            if inspect.isawaitable(target_user):
                target_user = await target_user
        else:
            target_user = None

        if target_user is None or target_user.is_active is False or target_user.is_deleted is True:
            raise ValueError(f"Cannot provision workspace: target owner user not found, inactive, or deleted: {effective_owner_id}")

        # 1. Generate unique deterministic slug
        slug = await self._generate_slug(name)

        # 2. Generate unique public Workspace ID
        public_id = await WorkspaceIdGenerator.generate_unique_public_id(
            workspace_repo=self.workspace_repo,
            name=name,
        )

        # Generate the UUID proactively to use it in prefixes
        workspace_id = uuid.uuid4()
        storage_prefix = f"workspace/{workspace_id}/"
        qdrant_namespace = f"workspace_{workspace_id.hex}"

        # Phase 1: Database Provisioning (inside transaction)
        workspace = Workspace(
            id=workspace_id,
            name=name,
            slug=slug,
            public_id=public_id,
            description=description,
            status=WorkspaceStatus.ACTIVE.value,
            provisioning_status=ProvisioningStatus.PENDING.value,
            storage_prefix=storage_prefix,
            qdrant_namespace=qdrant_namespace,
        )
        session.add(workspace)

        settings = WorkspaceSettings(
            workspace_id=workspace_id,
            settings_json={"features": ["core"]},
            schema_version=1
        )
        session.add(settings)

        member = WorkspaceMember(
            workspace_id=workspace_id,
            user_id=effective_owner_id,
            role=WorkspaceRole.OWNER.value,
            status=MemberStatus.ACTIVE.value,
            is_deleted=False,
        )
        session.add(member)

        audit_log = AuditLog(
            tenant_id=workspace_id,
            action="WORKSPACE_CREATED",
            user_id=effective_owner_id,
            resource_type="WORKSPACE",
            resource_id=str(workspace_id),
            details={"name": name, "slug": slug},
            status="success"
        )
        session.add(audit_log)

        # Flush to get records safely written
        await session.flush()

        # Move to PROVISIONING state
        workspace.provisioning_status = ProvisioningStatus.PROVISIONING.value
        await session.flush()

        # Phase 2: Async/External Provisioning
        try:
            # Prepare Object Storage prefix (logical allocation only)
            # Prepare Qdrant tenant isolation (logical allocation only)
            # In F3.1 this is logical; no physical calls fail here.

            # If everything succeeded:
            workspace.provisioning_status = ProvisioningStatus.READY.value
        except Exception:
            # If external provisioning failed:
            workspace.provisioning_status = ProvisioningStatus.FAILED.value
            raise

        # Commit phase 1
        await session.commit()
        await session.refresh(workspace)

        return workspace

    # Alias for create_workspace
    create_workspace = provision_workspace
