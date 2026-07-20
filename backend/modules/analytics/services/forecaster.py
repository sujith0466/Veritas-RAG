from backend.modules.analytics.schemas.analytics_dto import TrendForecastDTO

class TrendForecaster:
    def forecast_90_days(self, tenant_id: str, historical_cost_per_day: float, historical_tokens_per_day: float) -> TrendForecastDTO:
        # Simple linear projection
        projected_cost = historical_cost_per_day * 90
        projected_tokens = int(historical_tokens_per_day * 90)
        
        return TrendForecastDTO(
            tenant_id=tenant_id,
            projected_cost_90d_usd=projected_cost,
            projected_tokens_90d=projected_tokens
        )
