from backend.modules.dashboard.schemas.dashboard_dto import LiveDashboardEventDTO
import asyncio

class LiveEventBroadcaster:
    def __init__(self):
        self.connections: dict[str, list] = {}

    def connect(self, tenant_id: str, queue: asyncio.Queue):
        if tenant_id not in self.connections:
            self.connections[tenant_id] = []
        self.connections[tenant_id].append(queue)

    def disconnect(self, tenant_id: str, queue: asyncio.Queue):
        if tenant_id in self.connections and queue in self.connections[tenant_id]:
            self.connections[tenant_id].remove(queue)

    async def broadcast(self, tenant_id: str, event: LiveDashboardEventDTO):
        if tenant_id in self.connections:
            for queue in self.connections[tenant_id]:
                await queue.put(event)
