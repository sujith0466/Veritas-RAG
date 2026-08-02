import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

def main():
    print("Starting Milestone 20.2 Implementation...")

    # 1. injector.py
    with open("backend/core/chaos/injector.py", "w") as f:
        f.write("""import os
import asyncio
import random
from backend.core.chaos.models.fault_policy import FaultPolicyORM

class ChaosInjector:
    def __init__(self):
        # We assume RAGUARD_CHAOS_ENABLED flag is parsed elsewhere and passed,
        # but we also explicitly fence against the 'production' environment.
        self.is_production = os.getenv("ENVIRONMENT") == "production"
        self._mock_active_policies: dict[str, FaultPolicyORM] = {}
        
    def seed_mock_policy(self, token: str, policy: FaultPolicyORM):
        self._mock_active_policies[token] = policy

    async def check_fault_injection(self, chaos_token: str):
        if self.is_production:
            return # Safety net: Never execute in production
            
        policy = self._mock_active_policies.get(chaos_token)
        if not policy or not policy.is_active:
            return
            
        # Probability check
        if random.random() > policy.error_rate_pct:
            return
            
        if policy.fault_type == "LATENCY_SPIKE":
            await asyncio.sleep(policy.latency_ms / 1000.0)
        elif policy.fault_type == "LLM_HTTP_503":
            raise Exception("503 Service Unavailable: Simulated OpenAI Outage")
        elif policy.fault_type == "QDRANT_DISCONNECT":
            raise Exception("GRPCError: Simulated Vector Store Drop")
""")

    # 2. middleware.py
    with open("backend/core/chaos/middleware.py", "w") as f:
        f.write("""from backend.core.chaos.injector import ChaosInjector

class ChaosMiddleware:
    def __init__(self, injector: ChaosInjector):
        self.injector = injector

    async def process_request(self, headers: dict):
        token = headers.get("x-raguard-chaos-token")
        if token:
            await self.injector.check_fault_injection(token)
""")

    print("Milestone 20.2 completed.")

if __name__ == "__main__":
    main()
