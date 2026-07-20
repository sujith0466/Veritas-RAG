from backend.modules.query_rewrite.schemas.rewrite_dto import HyDEResponseDTO


class HyDERewriter:
    """Hypothetical Document Embeddings (HyDE) strategy.
    Generates a hallucinated answer to improve dense vector recall.
    """

    def __init__(self, llm_provider=None):
        self.llm_provider = llm_provider

    def rewrite(self, query: str) -> HyDEResponseDTO:
        """Generate a hypothetical document for the query."""
        
        # For M2, we mock the LLM call if provider is not yet injected.
        if self.llm_provider:
            # hypothetic_doc = self.llm_provider.generate(...)
            pass
            
        hypothetical_doc = f"This is a hypothetical technical explanation regarding {query}. It discusses the core concepts, mechanisms, and examples of {query} in detail."
        
        # We append the original query to the generated document to preserve exact keyword signals
        embedding_query = f"{query}\n\n{hypothetical_doc}"
        
        return HyDEResponseDTO(
            original_query=query,
            hypothetical_document=hypothetical_doc,
            embedding_query=embedding_query
        )
