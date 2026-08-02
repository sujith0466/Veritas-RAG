import os
import sys
import subprocess

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

# ---------------------------------------------------------------------------
# Milestone 16.4: Tests & Verification
# ---------------------------------------------------------------------------

def main():
    print("Starting Milestone 16.4 Implementation (Tests)...")
    os.makedirs("tests/unit/backend/modules/dashboard", exist_ok=True)
    os.makedirs("tests/integration", exist_ok=True)
    
    # 1. test_cache_service.py
    t_cache_path = "tests/unit/backend/modules/dashboard/test_cache_service.py"
    with open(t_cache_path, "w") as f:
        f.write("""import pytest
from backend.modules.dashboard.services.cache_service import RedisDashboardCache

@pytest.mark.asyncio
async def test_cache_service():
    cache = RedisDashboardCache()
    await cache.set("test_key", {"data": 123})
    val = await cache.get("test_key")
    assert val == {"data": 123}
    
    missing = await cache.get("wrong_key")
    assert missing is None
""")

    # 2. test_audit_export.py
    t_export_path = "tests/unit/backend/modules/dashboard/test_audit_export.py"
    with open(t_export_path, "w") as f:
        f.write("""import pytest
from backend.modules.dashboard.services.audit_export import AuditExportService
from backend.modules.dashboard.schemas.dashboard_dto import AuditExportRequestDTO

@pytest.mark.asyncio
async def test_audit_export():
    svc = AuditExportService()
    req = AuditExportRequestDTO(tenant_id="t1", window="24h")
    bundle = await svc.generate_export(req)
    
    assert bundle.record_count == 500
    assert bundle.download_url == "https://storage.raguard.ai/exports/t1/bundle.zip"
    assert len(bundle.checksum_sha256) == 64
""")

    # 3. test_live_feed.py
    t_feed_path = "tests/unit/backend/modules/dashboard/test_live_feed.py"
    with open(t_feed_path, "w") as f:
        f.write("""import pytest
import asyncio
from backend.modules.dashboard.services.live_feed import LiveEventBroadcaster
from backend.modules.dashboard.schemas.dashboard_dto import LiveDashboardEventDTO

@pytest.mark.asyncio
async def test_live_broadcaster():
    broadcaster = LiveEventBroadcaster()
    q1 = asyncio.Queue()
    q2 = asyncio.Queue()
    
    broadcaster.connect("t1", q1)
    broadcaster.connect("t1", q2)
    broadcaster.connect("t2", asyncio.Queue())
    
    event = LiveDashboardEventDTO(tenant_id="t1", event_type="TEST", payload={"msg": "hello"})
    await broadcaster.broadcast("t1", event)
    
    # Both q1 and q2 should get the event
    assert not q1.empty()
    assert not q2.empty()
    
    res = await q1.get()
    assert res.event_type == "TEST"
    
    broadcaster.disconnect("t1", q1)
    assert q1 not in broadcaster.connections["t1"]
""")

    print("Created test files.")
    
    print("Running tests...")
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/unit/backend/modules/dashboard"], capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        sys.exit(1)

    print("Milestone 16.4 completed.")

if __name__ == "__main__":
    main()
