import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

# ---------------------------------------------------------------------------
# Milestone 12.2: Validators (ClaimExtractor, CitationIntegrityChecker, NLI)
# ---------------------------------------------------------------------------

def main():
    print("Starting Milestone 12.2 Implementation...")

    # 1. claim_extractor.py
    extractor_path = "backend/modules/validation/services/claim_extractor.py"
    if not os.path.exists(extractor_path):
        with open(extractor_path, "w") as f:
            f.write("""import re

class ClaimExtractor:
    def __init__(self):
        self._sentence_split = re.compile(r'([A-Z][^.!?]*[.!?])', re.DOTALL)
        self._citation_marker = re.compile(r'\\[(\\d+)\\]')

    def extract_atomic_claims(self, answer_text: str) -> list[tuple[str, int | None]]:
        \"\"\"
        Splits answer text into sentences and extracts the associated citation marker.
        Returns a list of (sentence, citation_index) tuples.
        \"\"\"
        sentences = self._sentence_split.findall(answer_text)
        if not sentences:
            sentences = [answer_text]
            
        results = []
        for sentence in sentences:
            # Find all citation markers in the sentence
            markers = self._citation_marker.findall(sentence)
            if markers:
                # Use the first one for simplicity, or we could duplicate the claim per marker
                results.append((sentence.strip(), int(markers[0])))
            else:
                results.append((sentence.strip(), None))
                
        return [r for r in results if len(r[0]) > 3]
""")
        print("Created claim_extractor.py")

    # 2. citation_checker.py
    checker_path = "backend/modules/validation/services/citation_checker.py"
    if not os.path.exists(checker_path):
        with open(checker_path, "w") as f:
            f.write("""from backend.modules.generation.schemas.generation_dto import CitationDTO

class CitationIntegrityChecker:
    def verify_integrity(self, expected_citations: list[CitationDTO], actual_citations_used: list[int]) -> list[int]:
        \"\"\"
        Verifies that all citations referenced in the text actually exist in the GroundedAnswerDTO.
        Returns a list of invalid citation indices.
        \"\"\"
        valid_indices = {c.citation_index for c in expected_citations}
        invalid = []
        
        for idx in actual_citations_used:
            if idx is not None and idx not in valid_indices:
                invalid.append(idx)
                
        return invalid
""")
        print("Created citation_checker.py")

    # 3. providers/base.py
    with open("backend/modules/validation/providers/__init__.py", "w") as f:
        f.write('"""Validation providers."""\n')

    provider_base_path = "backend/modules/validation/providers/base.py"
    if not os.path.exists(provider_base_path):
        with open(provider_base_path, "w") as f:
            f.write("""from abc import ABC, abstractmethod
from backend.modules.validation.schemas.validation_dto import EntailmentVerdict

class NLIValidationProvider(ABC):
    @abstractmethod
    async def evaluate_entailment(self, premise: str, hypothesis: str) -> tuple[EntailmentVerdict, float]:
        \"\"\"
        Evaluates whether the premise entails the hypothesis.
        Returns:
            verdict: ENTAILED, NEUTRAL, or CONTRADICTED
            confidence: Float 0.0 to 1.0
        \"\"\"
        pass
""")
        print("Created providers/base.py")

    # 4. providers/cross_encoder_provider.py (stub implementation)
    provider_path = "backend/modules/validation/providers/cross_encoder_provider.py"
    if not os.path.exists(provider_path):
        with open(provider_path, "w") as f:
            f.write("""import re
from backend.modules.validation.providers.base import NLIValidationProvider
from backend.modules.validation.schemas.validation_dto import EntailmentVerdict

class MockCrossEncoderProvider(NLIValidationProvider):
    \"\"\"
    A heuristic-based mock NLI provider for baseline M12 implementation.
    A real implementation would use ONNX or an external API for distilroberta-nli.
    \"\"\"
    async def evaluate_entailment(self, premise: str, hypothesis: str) -> tuple[EntailmentVerdict, float]:
        if not premise or not hypothesis:
            return EntailmentVerdict.NEUTRAL, 1.0
            
        p_lower = premise.lower()
        h_lower = hypothesis.lower()
        
        p_words = set(re.findall(r'\\w+', p_lower))
        h_words = set(re.findall(r'\\w+', h_lower))
        
        stopwords = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'it', 'to', 'in', 'and'}
        p_core = p_words - stopwords
        h_core = h_words - stopwords
        
        if not h_core:
            return EntailmentVerdict.NEUTRAL, 1.0
            
        overlap = len(h_core.intersection(p_core)) / len(h_core)
        
        negation = re.compile(r'\\b(not|never|no|none)\\b')
        p_neg = bool(negation.search(p_lower))
        h_neg = bool(negation.search(h_lower))
        
        if overlap >= 0.6:
            if p_neg != h_neg:
                return EntailmentVerdict.CONTRADICTED, 0.9
            return EntailmentVerdict.ENTAILED, 0.85
        else:
            return EntailmentVerdict.NEUTRAL, 0.7
""")
        print("Created providers/cross_encoder_provider.py")

    # 5. nli_engine.py
    nli_path = "backend/modules/validation/services/nli_engine.py"
    if not os.path.exists(nli_path):
        with open(nli_path, "w") as f:
            f.write("""from backend.modules.validation.schemas.validation_dto import ClaimValidationItemDTO
from backend.modules.validation.providers.base import NLIValidationProvider
from backend.modules.generation.schemas.generation_dto import CitationDTO

class NLIValidationEngine:
    def __init__(self, provider: NLIValidationProvider):
        self.provider = provider

    async def validate_claims(
        self,
        extracted_claims: list[tuple[str, int | None]],
        citations: list[CitationDTO]
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
                verdict, confidence = self.provider.evaluate_entailment("", claim_text) # Will be NEUTRAL
            else:
                verdict, confidence = await self.provider.evaluate_entailment(excerpt, claim_text)
                
            results.append(
                ClaimValidationItemDTO(
                    claim_text=claim_text,
                    citation_index=citation_index,
                    excerpt=excerpt,
                    verdict=verdict,
                    confidence=confidence
                )
            )
            
        return results
""")
        print("Created nli_engine.py")

    print("Milestone 12.2 completed.")

if __name__ == "__main__":
    main()
