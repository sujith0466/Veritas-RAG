from backend.core.resilience.region_router import RegionRouter


class FailoverOrchestrator:
    def __init__(self, router: RegionRouter):
        self.router = router

    async def trigger_failover(self, target_region: str, force: bool = False) -> str:
        if target_region == self.router.active_region and not force:
            return "Already active"

        # Simulate health ping before switching
        # ...

        self.router.active_region = target_region
        return f"Failover successful to {target_region}"
