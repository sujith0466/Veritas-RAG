import asyncio

import pytest

from backend.modules.dashboard.schemas.dashboard_dto import LiveDashboardEventDTO
from backend.modules.dashboard.services.live_feed import LiveEventBroadcaster


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
