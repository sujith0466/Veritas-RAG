import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

def main():
    print("Starting Milestone 19.2 Implementation...")
    
    # 1. services/quota.py
    with open("backend/modules/analytics/services/quota.py", "w") as f:
        f.write("""from backend.modules.analytics.schemas.errors import QuotaExceededError

class QuotaGovernor:
    def __init__(self):
        self._mock_redis = {}
        # Pre-seed some mock quota limits
        self._mock_redis["quota:tokens:t1"] = 100000

    async def check_and_reserve(self, tenant_id: str, est_tokens: int) -> bool:
        key = f"quota:tokens:{tenant_id}"
        current = self._mock_redis.get(key, 0)
        
        if current < est_tokens:
            raise QuotaExceededError(f"Quota exhausted for tenant {tenant_id}")
            
        self._mock_redis[key] = current - est_tokens
        return True

    async def adjust_reservation_diff(self, tenant_id: str, diff_tokens: int):
        # Refund unused tokens, or subtract if underestimated
        key = f"quota:tokens:{tenant_id}"
        current = self._mock_redis.get(key, 0)
        self._mock_redis[key] = current + diff_tokens
""")

    # 2. services/roi.py
    with open("backend/modules/analytics/services/roi.py", "w") as f:
        f.write("""from backend.modules.analytics.schemas.analytics_dto import ROIAttributionDTO

class ROIAttributionEngine:
    def __init__(self, ticket_cost_usd: float = 18.50, incident_cost_usd: float = 250.00):
        self.ticket_cost_usd = ticket_cost_usd
        self.incident_cost_usd = incident_cost_usd

    def calculate_roi(self, tenant_id: str, queries_trusted: int, hallucinations_blocked: int, total_llm_cost_usd: float) -> ROIAttributionDTO:
        ticket_savings = queries_trusted * self.ticket_cost_usd
        incident_savings = hallucinations_blocked * self.incident_cost_usd
        net_roi = (ticket_savings + incident_savings) - total_llm_cost_usd
        
        return ROIAttributionDTO(
            tenant_id=tenant_id,
            window_days=30,
            queries_trusted=queries_trusted,
            hallucinations_blocked=hallucinations_blocked,
            ticket_savings_usd=ticket_savings,
            incident_savings_usd=incident_savings,
            total_llm_cost_usd=total_llm_cost_usd,
            net_roi_usd=net_roi
        )
""")

    print("Milestone 19.2 completed.")

if __name__ == "__main__":
    main()
