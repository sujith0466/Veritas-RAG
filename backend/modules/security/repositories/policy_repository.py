"""Policy Repository for PostgreSQL persistence."""

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.security.models.policy import Policy


class PolicyRepository:
    """PostgreSQL repository for tenant and workspace AI security policies."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_tenant_policy(self, tenant_id: str | UUID) -> Policy | None:
        """Fetch tenant-level policy where workspace_id IS NULL."""
        stmt = (
            select(Policy)
            .where(Policy.tenant_id == str(tenant_id))
            .where(Policy.workspace_id.is_(None))
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_workspace_policy(self, tenant_id: str | UUID, workspace_id: str | UUID) -> Policy | None:
        """Fetch workspace-specific policy override."""
        stmt = (
            select(Policy)
            .where(Policy.tenant_id == str(tenant_id))
            .where(Policy.workspace_id == str(workspace_id))
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def upsert_policy(
        self,
        tenant_id: str | UUID,
        workspace_id: str | UUID | None = None,
        max_tokens: int | None = None,
        blocked_topics: list[str] | None = None,
        redact_pii: bool | None = None,
        block_jailbreaks: bool | None = None,
    ) -> Policy:
        """Create or update a policy for a tenant or workspace."""
        if max_tokens is not None and max_tokens <= 0:
            raise ValueError("max_tokens must be a positive integer (> 0).")
        if blocked_topics is not None:
            if not all(isinstance(t, str) and t.strip() for t in blocked_topics):
                raise ValueError("blocked_topics must be a list of non-empty strings.")

        t_str = str(tenant_id)
        w_str = str(workspace_id) if workspace_id else None

        if w_str is None:
            policy = await self.get_tenant_policy(t_str)
        else:
            policy = await self.get_workspace_policy(t_str, w_str)

        if not policy:
            policy = Policy(
                tenant_id=t_str,
                workspace_id=w_str,
            )
            self.session.add(policy)

        if max_tokens is not None:
            policy.max_tokens = max_tokens
        if blocked_topics is not None:
            policy.blocked_topics = [t.strip() for t in blocked_topics if t.strip()]
        if redact_pii is not None:
            policy.redact_pii = redact_pii
        if block_jailbreaks is not None:
            policy.block_jailbreaks = block_jailbreaks

        await self.session.flush()
        return policy

    async def delete_policy(self, tenant_id: str | UUID, workspace_id: str | UUID | None = None) -> bool:
        """Delete a policy record."""
        t_str = str(tenant_id)
        w_str = str(workspace_id) if workspace_id else None

        if w_str is None:
            policy = await self.get_tenant_policy(t_str)
        else:
            policy = await self.get_workspace_policy(t_str, w_str)

        if policy:
            await self.session.delete(policy)
            await self.session.flush()
            return True
        return False
