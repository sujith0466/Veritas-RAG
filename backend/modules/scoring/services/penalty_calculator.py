from backend.modules.scoring.schemas.scoring_dto import ScoringInputsDTO

class PenaltyCalculator:
    def __init__(self):
        # Penalty points deducted per violation type
        self.penalty_unsupported_claim = 15.0
        self.penalty_invalid_citation = 10.0
        self.max_penalty = 100.0

    def calculate_penalty(self, inputs: ScoringInputsDTO) -> tuple[float, dict]:
        """
        Calculates score deductions based on discrete violations.
        Returns total deduction and breakdown.
        """
        unsupported_deduction = inputs.unsupported_claim_count * self.penalty_unsupported_claim
        invalid_cit_deduction = inputs.invalid_citation_count * self.penalty_invalid_citation
        
        total_deduction = min(unsupported_deduction + invalid_cit_deduction, self.max_penalty)
        
        breakdown = {
            "unsupported_claim_deduction": unsupported_deduction,
            "invalid_citation_deduction": invalid_cit_deduction,
            "total_deduction": total_deduction
        }
        
        return total_deduction, breakdown
