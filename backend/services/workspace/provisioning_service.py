import re
import uuid
import secrets
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.entities.workspace import Workspace, ProvisioningStatus, WorkspaceStatus
from backend.models.entities.workspace_settings import WorkspaceSettings
from backend.models.entities.workspace_member import WorkspaceMember
from backend.models.entities.audit_log import AuditLog
from backend.repositories.workspace import WorkspaceRepository
from backend.repositories.workspace_settings import WorkspaceSettingsRepository
from backend.repositories.workspace_member import WorkspaceMemberRepository


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
        self, session: AsyncSession, name: str, description: Optional[str], owner_user_id: uuid.UUID
    ) -> Workspace:
        """Provisions a new workspace with all associated resources."""
        
        # 1. Generate unique deterministic slug
        slug = await self._generate_slug(name)
        
        # Generate the UUID proactively to use it in prefixes
        workspace_id = uuid.uuid4()
        storage_prefix = f"workspace/{workspace_id}/"
        qdrant_namespace = f"workspace_{workspace_id.hex}"

        # Phase 1: Database Provisioning (inside transaction)
        workspace = Workspace(
            id=workspace_id,
            name=name,
            slug=slug,
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
            user_id=owner_user_id,
            role="OWNER"
        )
        session.add(member)

        audit_log = AuditLog(
            action="WORKSPACE_CREATED",
            user_id=owner_user_id,
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
        
        await session.commit()
        return workspace
