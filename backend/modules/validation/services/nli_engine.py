from backend.modules.generation.schemas.generation_dto import CitationDTO
from backend.modules.validation.providers.base import NLIValidationProvider
from backend.modules.validation.schemas.validation_dto import \
    ClaimValidationItemDTO


class NLIValidationEngine:
    def __init__(self, provider: NLIValidationProvider):
        self.provider = provider

    async def validate_claims(
        self,
        extracted_claims: list[tuple[str, int | None]],
        citations: list[CitationDTO],
    ) -> list[ClaimValidationItemDTO]:

        # Build map for O(1) lookup
        citation_map = {c.citation_index: c.excerpt for c in citations}

        results = []
        for claim_text, citation_index in extracted_claims:
            excerpt = None
            if citation_index is not None and citation_index in citation_map:
                excerpt = citation_map[citation_index]

            if not excerpt:
                # No evidence provided
                verdict, confidence = self.provider.evaluate_entailment(
                    "", claim_text
                )  # Will be NEUTRAL
            else:
                verdict, confidence = await self.provider.evaluate_entailment(
                    excerpt, claim_text
                )

            results.append(
                ClaimValidationItemDTO(
                    claim_text=claim_text,
                    citation_index=citation_index,
                    excerpt=excerpt,
                    verdict=verdict,
                    confidence_score=confidence,
                )
            )

        return results
