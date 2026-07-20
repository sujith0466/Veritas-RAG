from backend.modules.intelligence.schemas.intelligence_dto import OptimizationRecommendationDTO

class ThresholdOptimizer:
    def analyze_thresholds(self, tenant_id: str, historical_false_positives: int) -> OptimizationRecommendationDTO | None:
        if historical_false_positives > 100:
            return OptimizationRecommendationDTO(
                parameter_name="similarity_threshold",
                current_value=0.70,
                recommended_value=0.75,
                confidence_score=0.92,
                reason="High volume of false positives detected; tightening threshold."
            )
        return None
