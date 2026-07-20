from backend.modules.analytics.schemas.analytics_dto import ROIAttributionDTO

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
