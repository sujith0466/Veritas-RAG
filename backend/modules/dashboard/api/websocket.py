from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from backend.modules.dashboard.services.live_feed import LiveEventBroadcaster
import asyncio

router = APIRouter()
broadcaster = LiveEventBroadcaster()

@router.websocket("/ws/{tenant_id}")
async def websocket_endpoint(websocket: WebSocket, tenant_id: str):
    await websocket.accept()
    queue = asyncio.Queue()
    broadcaster.connect(tenant_id, queue)
    try:
        while True:
            event = await queue.get()
            await websocket.send_json(event.model_dump())
    except WebSocketDisconnect:
        broadcaster.disconnect(tenant_id, queue)
