from backend.core.chaos.injector import ChaosInjector


class ChaosMiddleware:
    def __init__(self, injector: ChaosInjector):
        self.injector = injector

    async def process_request(self, headers: dict):
        token = headers.get("x-raguard-chaos-token")
        if token:
            await self.injector.check_fault_injection(token)
