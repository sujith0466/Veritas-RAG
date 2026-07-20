import re
from backend.modules.query_rewrite.schemas.rewrite_dto import DecomposedQueriesDTO


class DecompositionRewriter:
    """Splits complex or multi-hop queries into independent search queries."""

    def __init__(self):
        # Basic heuristic splits for Milestone 2
        # In a full system, this calls an LLM prompt.
        self.split_pattern = re.compile(r'\b(?:and|compare|versus|vs|vs\.)\b', re.IGNORECASE)
        
    def decompose(self, query: str) -> DecomposedQueriesDTO:
        """Decompose a query if it contains multiple questions or comparison targets."""
        
        # Fast path for very short queries
        if len(query.split()) < 4:
            return DecomposedQueriesDTO(
                original_query=query,
                sub_queries=[query],
                is_complex=False
            )
            
        parts = self.split_pattern.split(query)
        cleaned_parts = [p.strip(" ?,.") for p in parts if len(p.strip()) > 3]
        
        if len(cleaned_parts) > 1:
            return DecomposedQueriesDTO(
                original_query=query,
                sub_queries=cleaned_parts,
                is_complex=True
            )
            
        return DecomposedQueriesDTO(
            original_query=query,
            sub_queries=[query],
            is_complex=False
        )
