import asyncio
import json
from typing import Any, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, status
from pydantic import ValidationError
import redis.asyncio as redis
import structlog

from backend.core.config import get_settings
from backend.core.security.jwt import get_jwt_service
from backend.models.entities.user import User
from backend.core.dependencies.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/notifications", tags=["Notifications"])

async def get_user_from_token(token: str, session: AsyncSession) -> Optional[User]:
    try:
        jwt_service = get_jwt_service()
        payload = await jwt_service.verify_token(token)
        user_id = payload.sub
        if not user_id:
            return None

        stmt = select(User).where(User.id == user_id, User.is_active == True)
        result = await session.execute(stmt)
        return result.scalars().first()
    except Exception:
        return None

@router.websocket("/ws")
async def websocket_notifications(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token for authentication"),
):
    """
    WebSocket endpoint for real-time in-app notifications via Redis Pub/Sub.
    """
    await websocket.accept()

    # 1. Authenticate the WebSocket connection
    async for session in get_db():
        user = await get_user_from_token(token, session)
        break
    if not user or not user.tenant_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token or missing tenant")
        return

    tenant_id = str(user.tenant_id)

    # 2. Connect to Redis Pub/Sub for the user's specific workspace
    settings = get_settings()
    redis_client = redis.from_url(settings.redis.redis_url)
    pubsub = redis_client.pubsub()

    channel_name = f"workspace:{tenant_id}:notifications"
    await pubsub.subscribe(channel_name)
    logger.info(f"WebSocket connected and subscribed to {channel_name} for user {user.id}")

    try:
        # Keep-alive loop to receive messages from Redis and push to WebSocket
        while True:
            # We use a small timeout to occasionally yield back
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message["type"] == "message":
                data = message["data"].decode("utf-8")
                await websocket.send_text(data)

            # Also occasionally check if the client closed the connection
            # by attempting to receive (we expect ping/pong or just wait)
            # Actually, `receive` would block forever if no message comes from client.
            # We can use asyncio.wait with FIRST_COMPLETED to wait for either redis or client.
            # But get_message with timeout is simpler and avoids complex tasks.
            # Let's just do a dummy receive with timeout to detect disconnects.
            try:
                # Use wait_for to quickly check if client disconnected
                await asyncio.wait_for(websocket.receive_text(), timeout=0.01)
            except asyncio.TimeoutError:
                pass # Normal, no message from client
            except WebSocketDisconnect:
                break # Client disconnected

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for user {user.id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except:
            pass
    finally:
        await pubsub.unsubscribe(channel_name)
        await pubsub.close()
        await redis_client.aclose()


# --- REST Endpoints for Notification Center & Navbar Bell ---

from backend.api.v1.schemas.notifications import (
    NotificationActionResponse,
    NotificationDTO,
    NotificationListResponse,
    UnreadCountResponse,
)
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.services.notification.notification_service import NotificationService
import uuid


def _to_uuid(val: Any) -> uuid.UUID:
    if isinstance(val, uuid.UUID):
        return val
    try:
        return uuid.UUID(str(val))
    except (ValueError, TypeError):
        return uuid.UUID("00000000-0000-0000-0000-000000000000")


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    category: Optional[str] = Query(None, description="Filter by category (SYSTEM, SECURITY, DOCUMENT, WORKSPACE)"),
    unread_only: bool = Query(False, description="Filter to only unread notifications"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> NotificationListResponse:
    """Retrieve paginated in-app notifications for the authenticated user and workspace."""
    service = NotificationService(session)
    return await service.list_notifications(
        tenant_id=_to_uuid(current_user.tenant_id),
        user_id=current_user.id,
        category=category,
        unread_only=unread_only,
        page=page,
        page_size=page_size,
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> UnreadCountResponse:
    """Retrieve accurate unread notification count for badge hydration."""
    service = NotificationService(session)
    return await service.get_unread_count(
        tenant_id=_to_uuid(current_user.tenant_id),
        user_id=current_user.id,
    )


@router.patch("/{notification_id}/read", response_model=NotificationDTO)
async def mark_notification_as_read(
    notification_id: uuid.UUID,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> NotificationDTO:
    """Mark a single notification as read."""
    service = NotificationService(session)
    result = await service.mark_as_read(
        notification_id=notification_id,
        tenant_id=_to_uuid(current_user.tenant_id),
        user_id=current_user.id,
    )
    if not result:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found or access denied",
        )
    return result


@router.post("/read-all", response_model=NotificationActionResponse)
async def mark_all_as_read(
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> NotificationActionResponse:
    """Mark all active notifications for the user as read."""
    service = NotificationService(session)
    return await service.mark_all_as_read(
        tenant_id=_to_uuid(current_user.tenant_id),
        user_id=current_user.id,
    )


@router.delete("/{notification_id}", response_model=NotificationActionResponse)
async def dismiss_notification(
    notification_id: uuid.UUID,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> NotificationActionResponse:
    """Dismiss (soft delete) a notification."""
    service = NotificationService(session)
    result = await service.dismiss_notification(
        notification_id=notification_id,
        tenant_id=_to_uuid(current_user.tenant_id),
        user_id=current_user.id,
    )
    if not result.success:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.message,
        )
    return result
