from abc import ABC, abstractmethod
from backend.modules.validation.schemas.validation_dto import EntailmentVerdict

class NLIValidationProvider(ABC):
    @abstractmethod
    async def evaluate_entailment(self, premise: str, hypothesis: str) -> tuple[EntailmentVerdict, float]:
        """
        Evaluates whether the premise entails the hypothesis.
        Returns:
            verdict: ENTAILED, NEUTRAL, or CONTRADICTED
            confidence: Float 0.0 to 1.0
        """
        pass
