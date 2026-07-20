import re

class CompletenessEvaluator:
    def __init__(self):
        # Naive requirement extraction logic using regex heuristics for now.
        # In a real provider-backed setup, this would use a lightweight LLM/NLI call.
        self._clause_split_pattern = re.compile(r'\b(and|or|with|including|specifically|about|on)\b', re.IGNORECASE)

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
        """
        Evaluates how well the answer_text addresses requirements in original_query.
        Returns:
            completeness_score (float): 0.0 to 1.0
            unaddressed_clauses (list[str]): Clauses not found
        """
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
            words = set(re.findall(r'\w+', clause.lower()))
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
