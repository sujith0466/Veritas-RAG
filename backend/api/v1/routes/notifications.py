import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, status
from pydantic import ValidationError
import redis.asyncio as redis

from backend.core.config import get_settings
from backend.services.auth.jwt_service import decode_access_token
from backend.models.entities.user import User
from backend.database.session import get_db_session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["Notifications"])

async def get_user_from_token(token: str, session: AsyncSession) -> Optional[User]:
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
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
    session_gen = get_db_session()
    session = await anext(session_gen)
    
    user = await get_user_from_token(token, session)
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
