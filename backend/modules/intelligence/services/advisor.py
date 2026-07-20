class IndexAdvisor:
    def analyze_index_health(self, tenant_id: str, avg_latency_ms: float) -> list[str]:
        actions = []
        if avg_latency_ms > 500:
            actions.append("Re-cluster vector database due to degraded latency.")
        return actions
