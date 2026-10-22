import json
from collections.abc import Callable, Coroutine
from typing import Any
import uuid

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import get_db
from backend.core.dependencies.workspace import get_workspace_member_or_raise
from backend.modules.analytics.services.quota import QuotaGovernor

logger = structlog.get_logger(__name__)


def enforce_workspace_quota(
    est_tokens: int | None = None,
) -> Callable[..., Coroutine[Any, Any, None]]:
    """FastAPI dependency to enforce monthly token quotas against PostgreSQL.

    Sequential enforcement: rejects requests with HTTP 429 when durable usage + estimate > limit.
    Never allows zero, negative, or malformed estimates to bypass quota enforcement.
    """
    if est_tokens is not None and (not isinstance(est_tokens, int) or est_tokens < 0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token estimate: must be a positive integer.",
        )

    async def _quota_guard(
        request: Request,
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

        # Compute defensible dynamic preflight token estimate from request body if available
        dynamic_tokens = 0
        try:
            body_bytes = await request.body()
            if body_bytes:
                payload = json.loads(body_bytes)
                if isinstance(payload, dict):
                    if "max_answer_tokens" in payload:
                        mat = payload.get("max_answer_tokens")
                        if not isinstance(mat, int) or mat <= 0:
                            raise HTTPException(
                                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail="max_answer_tokens must be a positive integer.",
                            )
                        max_output = mat
                    else:
                        max_output = 1024

                    query_str = str(payload.get("query") or "").strip()
                    input_tokens = max(1, len(query_str.split()) * 2) if query_str else 0

                    ev_chunks = payload.get("evidence_chunks")
                    if isinstance(ev_chunks, list):
                        input_tokens += sum(
                            max(1, len(str(c.get("content", "") if isinstance(c, dict) else getattr(c, "content", "")).split()) * 2)
                            for c in ev_chunks
                        )

                    if input_tokens > 0 or "max_answer_tokens" in payload:
                        dynamic_tokens = input_tokens + max_output
        except HTTPException:
            raise
        except Exception as parse_err:
            logger.debug("Could not parse request body for dynamic quota estimate", error=str(parse_err))

        if est_tokens is not None and est_tokens > 0:
            resolved_estimate = max(est_tokens, dynamic_tokens) if dynamic_tokens > 0 else est_tokens
        elif dynamic_tokens > 0:
            resolved_estimate = dynamic_tokens
        elif est_tokens == 0:
            resolved_estimate = 0
        else:
            resolved_estimate = 1024

        governor = QuotaGovernor()
        if target_ws_id is not None:
            result = await governor.check_hierarchical_quota(
                workspace_id=target_ws_id,
                user_id=current_user.id,
                requested_tokens=resolved_estimate,
                session=session,
            )
            if not result.is_allowed:
                logger.warning(
                    "Token quota exceeded for workspace %s, user %s. Blocked by: %s.",
                    target_ws_id,
                    current_user.id,
                    result.blocked_by,
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=result.detail or "Token quota exceeded",
                    headers={"Retry-After": "3600"},
                )
        else:
            # Fallback when only legacy tenant_id is available
            remaining = await governor.get_remaining_tokens(current_user.tenant_id or "default")
            check_thresh = resolved_estimate if resolved_estimate > 0 else 1
            if remaining < check_thresh:
                logger.warning(
                    "Tenant %s token quota exceeded. Blocking request with HTTP 429.",
                    current_user.tenant_id,
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Workspace token quota exceeded",
                    headers={"Retry-After": "3600"},
                )

    return _quota_guard
