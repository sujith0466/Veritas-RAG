import asyncio
import os
import re
import threading
from typing import Any

from structlog import get_logger

from backend.modules.validation.providers.base import NLIValidationProvider
from backend.modules.validation.schemas.validation_dto import EntailmentVerdict

logger = get_logger(__name__)

try:
    from sentence_transformers import CrossEncoder

    ST_AVAILABLE = True
except ImportError:
    CrossEncoder = None
    ST_AVAILABLE = False


class HeuristicNLIProvider(NLIValidationProvider):
    """Deterministic lexical overlap & negation heuristic NLI provider.

    Used as an authoritative zero-dependency baseline and graceful fallback when
    neural cross-encoder weights or ML inference dependencies are unavailable.
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


# Backward-compatible alias for existing imports
MockCrossEncoderProvider = HeuristicNLIProvider


class LocalCrossEncoderNLIProvider(NLIValidationProvider):
    """Neural 3-class NLI provider backed by sentence-transformers CrossEncoder.

    Executes sequence classification over (premise, hypothesis) pairs to determine
    ENTAILED, CONTRADICTED, or NEUTRAL relationships with calibrated softmax confidence.
    """

    def __init__(
        self,
        model_name: str | None = None,
        model: Any | None = None,
        fallback_provider: NLIValidationProvider | None = None,
        max_concurrency: int = 4,
    ) -> None:
        self.model_name = model_name or os.getenv(
            "RAGUARD_NLI_MODEL", "cross-encoder/nli-distilroberta-base"
        )
        self._model = model
        self._fallback = fallback_provider or HeuristicNLIProvider()
        self._lock = threading.Lock()
        self._inference_lock = threading.Semaphore(max_concurrency)
        self._label_mapping: dict[int, EntailmentVerdict] | None = None

    def _get_model(self) -> Any:
        if self._model is not None:
            return self._model
        if not ST_AVAILABLE:
            raise RuntimeError(
                "sentence_transformers is not installed or available in runtime."
            )

        with self._lock:
            if self._model is not None:
                return self._model

            try:
                self._model = CrossEncoder(self.model_name)
                self._resolve_label_mapping()
                return self._model
            except Exception as exc:
                logger.warning(
                    "Failed to load local NLI CrossEncoder model, falling back to heuristic",
                    model_name=self.model_name,
                    error=str(exc),
                )
                raise

    def _resolve_label_mapping(self) -> dict[int, EntailmentVerdict]:
        """Dynamically inspect model config id2label metadata for 3-class NLI mapping."""
        if self._label_mapping is not None:
            return self._label_mapping

        mapping: dict[int, EntailmentVerdict] = {}
        model_obj = getattr(self._model, "model", self._model)
        config = getattr(model_obj, "config", None)
        id2label = getattr(config, "id2label", None) if config else None

        if id2label and isinstance(id2label, dict):
            for idx, label_str in id2label.items():
                try:
                    int_idx = int(idx)
                except (ValueError, TypeError):
                    continue
                lbl_lower = str(label_str).lower()
                if "entail" in lbl_lower:
                    mapping[int_idx] = EntailmentVerdict.ENTAILED
                elif "contra" in lbl_lower:
                    mapping[int_idx] = EntailmentVerdict.CONTRADICTED
                elif "neut" in lbl_lower:
                    mapping[int_idx] = EntailmentVerdict.NEUTRAL

        # Fallback to standard MNLI convention if dynamic mapping is incomplete
        if len(mapping) < 3:
            mapping = {
                0: EntailmentVerdict.CONTRADICTED,
                1: EntailmentVerdict.ENTAILED,
                2: EntailmentVerdict.NEUTRAL,
            }

        self._label_mapping = mapping
        return mapping

    def _predict_sync(self, premise: str, hypothesis: str) -> tuple[EntailmentVerdict, float]:
        import numpy as np

        model = self._get_model()
        mapping = self._resolve_label_mapping()

        with self._inference_lock:
            try:
                scores = model.predict([(premise, hypothesis)], apply_softmax=True)
            except TypeError:
                raw = model.predict([(premise, hypothesis)])
                raw_arr = np.array(raw)
                exp_scores = np.exp(raw_arr - np.max(raw_arr, axis=-1, keepdims=True))
                scores = exp_scores / np.sum(exp_scores, axis=-1, keepdims=True)

        probs = np.array(scores)
        if probs.ndim > 1:
            probs = probs[0]

        best_idx = int(np.argmax(probs))
        verdict = mapping.get(best_idx, EntailmentVerdict.NEUTRAL)
        confidence = float(np.clip(probs[best_idx], 0.0, 1.0))

        return verdict, round(confidence, 4)

    async def evaluate_entailment(
        self, premise: str, hypothesis: str
    ) -> tuple[EntailmentVerdict, float]:
        if not premise or not hypothesis:
            return EntailmentVerdict.NEUTRAL, 1.0

        try:
            return await asyncio.to_thread(self._predict_sync, premise, hypothesis)
        except Exception as exc:
            logger.warning(
                "LocalCrossEncoderNLIProvider inference exception; falling back to heuristic",
                model_name=self.model_name,
                error=str(exc),
            )
            return await self._fallback.evaluate_entailment(premise, hypothesis)
