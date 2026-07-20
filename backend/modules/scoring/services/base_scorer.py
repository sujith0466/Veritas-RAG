from backend.modules.scoring.schemas.scoring_dto import ScoringInputsDTO

class BaseReliabilityScorer:
    def __init__(self):
        # Weights for the base score calculation (must sum to 1.0)
        self.w_relevance = 0.25
        self.w_entailment = 0.40
        self.w_evidence = 0.20
        self.w_completeness = 0.15

    def calculate_base_score(self, inputs: ScoringInputsDTO) -> float:
        """
        Calculates the weighted base reliability score (0-100).
        """
        raw_score = (
            (inputs.retrieval_relevance_score * self.w_relevance) +
            (inputs.validation_entailment_ratio * self.w_entailment) +
            (inputs.confidence_evidence_strength * self.w_evidence) +
            (inputs.reflection_completeness * self.w_completeness)
        )
        return min(max(raw_score * 100.0, 0.0), 100.0)
