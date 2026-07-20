import re
from backend.modules.query_rewrite.schemas.rewrite_dto import ClarificationQuestionDTO


class DisambiguationRewriter:
    """Identifies ambiguous queries and generates clarification options."""

    def __init__(self):
        # Basic acronyms/ambiguous terms for heuristic detection
        self.ambiguous_terms = {
            "apple": ["Apple Inc. (Technology)", "Apple (Fruit)"],
            "amazon": ["Amazon (Company)", "Amazon (River/Rainforest)"],
            "model": ["Machine Learning Model", "Data Model", "Business Model"],
            "architecture": ["Software Architecture", "Building Architecture"]
        }

    def generate_clarification(self, query: str) -> ClarificationQuestionDTO | None:
        """Return a clarification question if the query is ambiguous, else None."""
        
        query_lower = query.lower()
        
        for term, options in self.ambiguous_terms.items():
            if re.search(rf'\b{term}\b', query_lower):
                return ClarificationQuestionDTO(
                    question_text=f"Your query mentions '{term}', which can be ambiguous. Which did you mean?",
                    options=options
                )
                
        # If very short query with no verb, it might also be ambiguous
        words = query_lower.split()
        if len(words) <= 2:
            return ClarificationQuestionDTO(
                question_text=f"'{query}' is quite broad. Could you specify which aspect you are interested in?",
                options=["Configuration & Setup", "Troubleshooting", "General Overview"]
            )
            
        return None
