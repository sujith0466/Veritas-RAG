class RegionRouter:
    def __init__(self):
        self.active_region = "us-east-1"
        self.secondary_region = "eu-west-1"

    def route_request(self) -> str:
        # In a real system, this might look up current traffic weights or health checks
        return self.active_region
