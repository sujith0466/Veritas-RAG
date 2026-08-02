import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

# ---------------------------------------------------------------------------
# Milestone 11.2: Completeness Evaluator & Logical Consistency Reviewer
# ---------------------------------------------------------------------------

def main():
    print("Starting Milestone 11.2 Implementation...")
    os.makedirs("backend/modules/reflection/services", exist_ok=True)

    # 1. Create completeness_evaluator.py
    completeness_path = "backend/modules/reflection/services/completeness_evaluator.py"
    if not os.path.exists(completeness_path):
        with open(completeness_path, "w") as f:
            f.write("""import re

class CompletenessEvaluator:
    def __init__(self):
        # Naive requirement extraction logic using regex heuristics for now.
        # In a real provider-backed setup, this would use a lightweight LLM/NLI call.
        self._clause_split_pattern = re.compile(r'\\b(and|or|with|including|specifically|about|on)\\b', re.IGNORECASE)

    def extract_clauses(self, original_query: str) -> list[str]:
        # Simple heuristic to split query into constituent requirements
        parts = self._clause_split_pattern.split(original_query)
        clauses = []
        current = ""
        for part in parts:
            if part.lower() in ('and', 'or', 'with', 'including', 'specifically', 'about', 'on'):
                if current.strip():
                    clauses.append(current.strip())
                current = ""
            else:
                current += part + " "
        if current.strip():
            clauses.append(current.strip())
        return [c for c in clauses if len(c) > 3]

    async def evaluate(self, original_query: str, answer_text: str) -> tuple[float, list[str]]:
        \"\"\"
        Evaluates how well the answer_text addresses requirements in original_query.
        Returns:
            completeness_score (float): 0.0 to 1.0
            unaddressed_clauses (list[str]): Clauses not found
        \"\"\"
        if not original_query.strip():
            return 1.0, []
            
        clauses = self.extract_clauses(original_query)
        if not clauses:
            clauses = [original_query]
            
        addressed = []
        unaddressed = []
        
        answer_lower = answer_text.lower()
        
        for clause in clauses:
            # Very basic keyword overlap check.
            words = set(re.findall(r'\\w+', clause.lower()))
            # Remove common stop words for naive evaluation
            stop_words = {'what', 'is', 'the', 'how', 'why', 'who', 'where', 'when', 'a', 'an', 'to', 'in', 'for', 'of'}
            key_words = words - stop_words
            
            if not key_words:
                addressed.append(clause)
                continue
                
            # If at least half the non-stop words exist in the answer, consider it addressed
            match_count = sum(1 for w in key_words if w in answer_lower)
            if match_count >= len(key_words) / 2.0:
                addressed.append(clause)
            else:
                unaddressed.append(clause)
                
        score = len(addressed) / len(clauses) if clauses else 1.0
        return score, unaddressed
""")
        print("Created completeness_evaluator.py")
    else:
        print("completeness_evaluator.py already exists")

    # 2. Create logical_reviewer.py
    reviewer_path = "backend/modules/reflection/services/logical_reviewer.py"
    if not os.path.exists(reviewer_path):
        with open(reviewer_path, "w") as f:
            f.write("""import re
from backend.modules.reflection.schemas.reflection_dto import ClaimValidationResultDTO

class LogicalConsistencyReviewer:
    def __init__(self):
        # Naive negation check for contradiction.
        # In a real setup, an NLI (Natural Language Inference) model would do this.
        self._negation_pattern = re.compile(r'\\b(not|never|no|none|false|fake|invalid)\\b', re.IGNORECASE)

    async def review(self, claim_results: list[ClaimValidationResultDTO], citations: list[str]) -> tuple[float, list[str]]:
        \"\"\"
        Reviews claim pairs for internal logical contradictions.
        Returns:
            consistency_score (float): 0.0 to 1.0
            contradictions_found (list[str]): Descriptions of conflicts
        \"\"\"
        if len(claim_results) < 2:
            return 1.0, []

        contradictions = []
        claims = [c.claim_text.lower() for c in claim_results]

        for i in range(len(claims)):
            for j in range(i + 1, len(claims)):
                c1 = claims[i]
                c2 = claims[j]
                
                # Simple heuristic: exact same core words, but one is negated
                words1 = set(re.findall(r'\\w+', c1))
                words2 = set(re.findall(r'\\w+', c2))
                
                neg1 = bool(self._negation_pattern.search(c1))
                neg2 = bool(self._negation_pattern.search(c2))
                
                core1 = words1 - {'not', 'never', 'no', 'none', 'false', 'fake', 'invalid', 'is', 'are', 'was', 'were'}
                core2 = words2 - {'not', 'never', 'no', 'none', 'false', 'fake', 'invalid', 'is', 'are', 'was', 'were'}
                
                # If core words are >80% overlapping but negation state differs -> potential contradiction
                if not core1 or not core2:
                    continue
                    
                overlap = len(core1.intersection(core2))
                max_len = max(len(core1), len(core2))
                
                if overlap / max_len > 0.8 and neg1 != neg2:
                    contradictions.append(f"Contradiction between Claim {i+1} and Claim {j+1}")

        # Reduce score based on contradictions
        total_pairs = (len(claims) * (len(claims) - 1)) / 2
        inconsistent_pairs = len(contradictions)
        
        score = 1.0 - (inconsistent_pairs / total_pairs)
        return max(0.0, score), contradictions
""")
        print("Created logical_reviewer.py")
    else:
        print("logical_reviewer.py already exists")

    print("Milestone 11.2 completed.")

if __name__ == "__main__":
    main()
