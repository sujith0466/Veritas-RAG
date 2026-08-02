import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

# ---------------------------------------------------------------------------
# Milestone 13.2: Scoring Math & Adjustments
# ---------------------------------------------------------------------------

def main():
    print("Starting Milestone 13.2 Implementation...")
    
    # 1. base_scorer.py
    scorer_path = "backend/modules/scoring/services/base_scorer.py"
    if not os.path.exists(scorer_path):
        with open(scorer_path, "w") as f:
            f.write("""from backend.modules.scoring.schemas.scoring_dto import ScoringInputsDTO

class BaseReliabilityScorer:
    def __init__(self):
        # Weights for the base score calculation (must sum to 1.0)
        self.w_relevance = 0.25
        self.w_entailment = 0.40
        self.w_evidence = 0.20
        self.w_completeness = 0.15

    def calculate_base_score(self, inputs: ScoringInputsDTO) -> float:
        \"\"\"
        Calculates the weighted base reliability score (0-100).
        \"\"\"
        raw_score = (
            (inputs.retrieval_relevance_score * self.w_relevance) +
            (inputs.validation_entailment_ratio * self.w_entailment) +
            (inputs.confidence_evidence_strength * self.w_evidence) +
            (inputs.reflection_completeness * self.w_completeness)
        )
        return min(max(raw_score * 100.0, 0.0), 100.0)
""")
        print("Created base_scorer.py")

    # 2. penalty_calculator.py
    penalty_path = "backend/modules/scoring/services/penalty_calculator.py"
    if not os.path.exists(penalty_path):
        with open(penalty_path, "w") as f:
            f.write("""from backend.modules.scoring.schemas.scoring_dto import ScoringInputsDTO

class PenaltyCalculator:
    def __init__(self):
        # Penalty points deducted per violation type
        self.penalty_unsupported_claim = 15.0
        self.penalty_invalid_citation = 10.0
        self.max_penalty = 100.0

    def calculate_penalty(self, inputs: ScoringInputsDTO) -> tuple[float, dict]:
        \"\"\"
        Calculates score deductions based on discrete violations.
        Returns total deduction and breakdown.
        \"\"\"
        unsupported_deduction = inputs.unsupported_claim_count * self.penalty_unsupported_claim
        invalid_cit_deduction = inputs.invalid_citation_count * self.penalty_invalid_citation
        
        total_deduction = min(unsupported_deduction + invalid_cit_deduction, self.max_penalty)
        
        breakdown = {
            "unsupported_claim_deduction": unsupported_deduction,
            "invalid_citation_deduction": invalid_cit_deduction,
            "total_deduction": total_deduction
        }
        
        return total_deduction, breakdown
""")
        print("Created penalty_calculator.py")

    print("Milestone 13.2 completed.")

if __name__ == "__main__":
    main()
