import re

from backend.modules.validation.providers.base import NLIValidationProvider
from backend.modules.validation.schemas.validation_dto import EntailmentVerdict


class MockCrossEncoderProvider(NLIValidationProvider):
    """
    A heuristic-based mock NLI provider for baseline M12 implementation.
    A real implementation would use ONNX or an external API for distilroberta-nli.
    """

    async def evaluate_entailment(
        self, premise: str, hypothesis: str
    ) -> tuple[EntailmentVerdict, float]:
        if not premise or not hypothesis:
            return EntailmentVerdict.NEUTRAL, 1.0

        p_lower = premise.lower()
        h_lower = hypothesis.lower()

        p_words = set(re.findall(r"\w+", p_lower))
        h_words = set(re.findall(r"\w+", h_lower))

        stopwords = {
            "the",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "it",
            "to",
            "in",
            "and",
        }
        p_core = p_words - stopwords
        h_core = h_words - stopwords

        if not h_core:
            return EntailmentVerdict.NEUTRAL, 1.0

        overlap = len(h_core.intersection(p_core)) / len(h_core)

        negation = re.compile(r"\b(not|never|no|none)\b")
        p_neg = bool(negation.search(p_lower))
        h_neg = bool(negation.search(h_lower))

        if overlap >= 0.6:
            if p_neg != h_neg:
                return EntailmentVerdict.CONTRADICTED, 0.9
            return EntailmentVerdict.ENTAILED, 0.85
        return EntailmentVerdict.NEUTRAL, 0.7
