import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

# ---------------------------------------------------------------------------
# Milestone 16.3: Live Feed & Websockets
# ---------------------------------------------------------------------------

def main():
    print("Starting Milestone 16.3 Implementation...")

    # 1. services/live_feed.py
    feed_path = "backend/modules/dashboard/services/live_feed.py"
    with open(feed_path, "w") as f:
        f.write("""from backend.modules.dashboard.schemas.dashboard_dto import LiveDashboardEventDTO
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
""")

    # 2. api/routes.py
    with open("backend/modules/dashboard/api/__init__.py", "w") as f:
        f.write('"""Dashboard API routes."""\n')

    routes_path = "backend/modules/dashboard/api/routes.py"
    with open(routes_path, "w") as f:
        f.write("""from fastapi import APIRouter, Depends, HTTPException
from backend.modules.dashboard.schemas.dashboard_dto import (
    ExecutiveDashboardDTO, SLAComplianceReportDTO, HallucinationTrendDTO,
    AuditExportRequestDTO, AuditExportBundleDTO
)
from backend.modules.dashboard.services.dashboard_service import DashboardService
from backend.modules.dashboard.services.cache_service import RedisDashboardCache
from backend.modules.dashboard.services.audit_export import AuditExportService
from typing import List

router = APIRouter(prefix="/dashboard/v1", tags=["Dashboard"])

def get_dashboard_service():
    # In production, inject proper dependencies
    return DashboardService(RedisDashboardCache())

def get_audit_service():
    return AuditExportService()

@router.get("/executive/{tenant_id}", response_model=ExecutiveDashboardDTO)
async def get_executive(tenant_id: str, svc: DashboardService = Depends(get_dashboard_service)):
    return await svc.get_executive_dashboard(tenant_id)

@router.get("/governance/{tenant_id}", response_model=SLAComplianceReportDTO)
async def get_governance(tenant_id: str, window: str = "24h", svc: DashboardService = Depends(get_dashboard_service)):
    return await svc.get_governance_report(tenant_id, window)

@router.get("/trends/{tenant_id}", response_model=List[HallucinationTrendDTO])
async def get_trends(tenant_id: str, window: str = "7d", svc: DashboardService = Depends(get_dashboard_service)):
    return await svc.get_trust_trends(tenant_id, window)

@router.post("/export", response_model=AuditExportBundleDTO)
async def export_audit(request: AuditExportRequestDTO, svc: AuditExportService = Depends(get_audit_service)):
    return await svc.generate_export(request)
""")

    # 3. api/websocket.py
    ws_path = "backend/modules/dashboard/api/websocket.py"
    with open(ws_path, "w") as f:
        f.write("""from fastapi import APIRouter, WebSocket, WebSocketDisconnect
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
""")

    print("Milestone 16.3 completed.")

if __name__ == "__main__":
    main()
