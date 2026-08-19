from collections.abc import Callable, Coroutine
import logging
from typing import Any
import uuid

from fastapi import Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import get_db
from backend.core.dependencies.workspace import get_workspace_member_or_raise
from backend.modules.analytics.services.quota import QuotaGovernor

logger = logging.getLogger(__name__)


def enforce_workspace_quota(est_tokens: int = 0) -> Callable[..., Coroutine[Any, Any, None]]:
    """FastAPI dependency to enforce monthly token quotas against PostgreSQL.

    Sequential enforcement: rejects requests with HTTP 429 when durable usage >= limit.
    """
    async def _quota_guard(
        workspace_id: uuid.UUID | None = None,
        current_user: UserContext = Depends(get_current_user),
        session: AsyncSession = Depends(get_db),
    ) -> None:
        target_ws_id = workspace_id
        if target_ws_id is None:
            # Fallback resolution from user context
            user_ws = getattr(current_user, "workspace_id", None)
            if user_ws:
                if isinstance(user_ws, uuid.UUID):
                    target_ws_id = user_ws
                else:
                    try:
                        target_ws_id = uuid.UUID(str(user_ws))
                    except (ValueError, TypeError):
                        pass

        if target_ws_id is None and current_user.tenant_id:
            try:
                target_ws_id = uuid.UUID(str(current_user.tenant_id))
            except (ValueError, TypeError):
                pass

        # If target workspace is known, verify authorization
        if target_ws_id is not None:
            await get_workspace_member_or_raise(target_ws_id, current_user, session)

        governor = QuotaGovernor()
        if target_ws_id is not None:
            is_exceeded, used, limit, is_hard = await governor.check_quota(
                workspace_id=target_ws_id,
                tenant_id=current_user.tenant_id,
                session=session,
            )
        else:
            # Fallback when only legacy tenant_id is available
            remaining = await governor.get_remaining_tokens(current_user.tenant_id or "default")
            is_exceeded = (remaining <= 0)

        if is_exceeded:
            logger.warning(
                "Workspace %s token quota exceeded. Blocking request with HTTP 429.",
                target_ws_id or current_user.tenant_id,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Workspace token quota exceeded",
                headers={"Retry-After": "3600"},
            )

    return _quota_guard
