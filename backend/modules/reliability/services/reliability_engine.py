import re

from backend.modules.retrieval.schemas.retrieval_dto import RankedEvidenceDTO
from backend.ai.interfaces.llm_provider import LLMRequest


class ReliabilityEngine:
    """Incremental Reliability Engine for F8.7."""
    def __init__(self, llm_provider=None):
        self.ema_alpha = 0.3
        self.current_score = 1.0
        self.llm_provider = llm_provider

    async def evaluate_incremental(self, sentence: str, evidence: list[RankedEvidenceDTO]) -> float:
        """
        Evaluate a single sentence against the evidence using semantic evaluation.
        Returns the new Exponential Moving Average score.
        """
        if not evidence or not self.llm_provider:
            return self.current_score

        # Fast normalization to check if sentence is substantial
        sent_words = set(re.findall(r'\b\w+\b', sentence.lower()))
        if len(sent_words) < 3:
            return self.current_score

        # Prepare evidence block
        evidence_text = "\n".join(
            [str(chunk.content if hasattr(chunk, "content") else chunk.get("content", "")) for chunk in evidence]
        )

        prompt = f"""Evaluate if the following sentence is supported by the evidence.
Evidence:
{evidence_text}

Sentence:
{sentence}

Reply ONLY with a float between 0.0 and 1.0 representing the reliability score. 1.0 means fully supported, 0.0 means completely unsupported or hallucinated."""

        req = LLMRequest(
            prompt=prompt,
            system_instruction="You are a strict fact-checking evaluator. Reply ONLY with a float like 0.8.",
            tenant_id="system",
            workspace_id="system",
            temperature=0.0
        )

        try:
            resp = await self.llm_provider.generate(req)
            score_match = re.search(r'0\.\d+|1\.0|0', resp.content)
            if score_match:
                sentence_reliability = float(score_match.group())
            else:
                sentence_reliability = 0.5 # Fail-safe intermediate
        except Exception:
            sentence_reliability = 0.5 # Fail-safe intermediate

        # EMA
        self.current_score = (self.ema_alpha * sentence_reliability) + ((1 - self.ema_alpha) * self.current_score)
        return self.current_score
