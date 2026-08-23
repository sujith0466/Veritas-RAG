"""Targeted unit tests for NLI Cross-Encoder Provider and Validation Engine (ISS-008)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from backend.modules.generation.schemas.generation_dto import CitationDTO, GroundedAnswerDTO
from backend.modules.validation.providers.cross_encoder_provider import (
    HeuristicNLIProvider,
    LocalCrossEncoderNLIProvider,
    MockCrossEncoderProvider,
)
from backend.modules.validation.schemas.validation_dto import (
    EntailmentVerdict,
    ValidationRequestDTO,
)
from backend.modules.validation.services.nli_engine import NLIValidationEngine
from backend.modules.validation.services.validation_engine import ValidationEngine


class FakeCrossEncoderModel:
    """Controllable mock for sentence_transformers CrossEncoder."""

    def __init__(self, return_scores: list[list[float]] | None = None, id2label: dict[int, str] | None = None):
        self.return_scores = return_scores or [[0.1, 0.85, 0.05]]
        self.call_count = 0
        self.config = MagicMock()
        self.config.id2label = id2label or {0: "contradiction", 1: "entailment", 2: "neutral"}

    def predict(self, pairs: list[tuple[str, str]], apply_softmax: bool = True):
        self.call_count += 1
        return self.return_scores


@pytest.mark.asyncio
async def test_nli_01_provider_initialization():
    """NLI-01: LocalCrossEncoderNLIProvider initializes cleanly with custom or default model name."""
    provider = LocalCrossEncoderNLIProvider(model_name="test-nli-model")
    assert provider.model_name == "test-nli-model"
    assert isinstance(provider._fallback, HeuristicNLIProvider)


@pytest.mark.asyncio
async def test_nli_02_entailed_mapping():
    """NLI-02: Predicts ENTAILED verdict when entailment probability dominates."""
    # Index 1 is entailment with 0.92 probability
    fake_model = FakeCrossEncoderModel(return_scores=[[0.03, 0.92, 0.05]])
    provider = LocalCrossEncoderNLIProvider(model=fake_model)

    verdict, confidence = await provider.evaluate_entailment(
        "Paris is the capital of France.",
        "Paris is in France."
    )

    assert verdict == EntailmentVerdict.ENTAILED
    assert confidence == 0.92


@pytest.mark.asyncio
async def test_nli_03_contradicted_mapping():
    """NLI-03: Predicts CONTRADICTED verdict when contradiction probability dominates."""
    # Index 0 is contradiction with 0.88 probability
    fake_model = FakeCrossEncoderModel(return_scores=[[0.88, 0.02, 0.10]])
    provider = LocalCrossEncoderNLIProvider(model=fake_model)

    verdict, confidence = await provider.evaluate_entailment(
        "Water boils at 100 degrees Celsius.",
        "Water boils at 0 degrees Celsius."
    )

    assert verdict == EntailmentVerdict.CONTRADICTED
    assert confidence == 0.88


@pytest.mark.asyncio
async def test_nli_04_neutral_mapping():
    """NLI-04: Predicts NEUTRAL verdict when neutral probability dominates."""
    # Index 2 is neutral with 0.79 probability
    fake_model = FakeCrossEncoderModel(return_scores=[[0.05, 0.16, 0.79]])
    provider = LocalCrossEncoderNLIProvider(model=fake_model)

    verdict, confidence = await provider.evaluate_entailment(
        "I bought an apple at the store.",
        "The apple was delicious and sweet."
    )

    assert verdict == EntailmentVerdict.NEUTRAL
    assert confidence == 0.79


@pytest.mark.asyncio
async def test_nli_05_confidence_bounds():
    """NLI-05: Confidence is strictly bounded between 0.0 and 1.0."""
    fake_model = FakeCrossEncoderModel(return_scores=[[0.1, 0.7, 0.2]])
    provider = LocalCrossEncoderNLIProvider(model=fake_model)

    _, conf = await provider.evaluate_entailment("Premise text", "Hypothesis text")
    assert 0.0 <= conf <= 1.0


@pytest.mark.asyncio
async def test_nli_06_model_unavailable_fallback():
    """NLI-06: Automatically falls back to HeuristicNLIProvider when sentence_transformers model cannot load."""
    with patch("backend.modules.validation.providers.cross_encoder_provider.ST_AVAILABLE", False):
        provider = LocalCrossEncoderNLIProvider()
        verdict, conf = await provider.evaluate_entailment(
            "The sky is clear and blue today.",
            "The sky is blue today."
        )
        assert verdict == EntailmentVerdict.ENTAILED
        assert 0.0 <= conf <= 1.0


@pytest.mark.asyncio
async def test_nli_07_inference_exception_fallback():
    """NLI-07: Automatically falls back to heuristic provider on runtime inference exception."""
    failing_model = MagicMock()
    failing_model.predict.side_effect = RuntimeError("GPU out of memory")
    provider = LocalCrossEncoderNLIProvider(model=failing_model)

    verdict, conf = await provider.evaluate_entailment(
        "PostgreSQL supports relational queries.",
        "PostgreSQL supports relational database queries."
    )
    assert verdict == EntailmentVerdict.ENTAILED
    assert 0.0 <= conf <= 1.0


@pytest.mark.asyncio
async def test_nli_08_empty_premise_hypothesis():
    """NLI-08: Empty premise or hypothesis immediately returns (NEUTRAL, 1.0)."""
    provider = LocalCrossEncoderNLIProvider()
    v1, c1 = await provider.evaluate_entailment("", "Some claim")
    assert v1 == EntailmentVerdict.NEUTRAL
    assert c1 == 1.0

    v2, c2 = await provider.evaluate_entailment("Some premise", "")
    assert v2 == EntailmentVerdict.NEUTRAL
    assert c2 == 1.0


@pytest.mark.asyncio
async def test_nli_09_missing_await_regression():
    """NLI-09: Verifies that empty-excerpt claim validation awaits evaluate_entailment without coroutine error."""
    provider = HeuristicNLIProvider()
    engine = NLIValidationEngine(provider)

    claims = [("Unsupported statement without citation.", None)]
    citations = []

    # If missing await, this would fail when storing verdict in ClaimValidationItemDTO
    results = await engine.validate_claims(claims, citations)
    assert len(results) == 1
    assert results[0].verdict == EntailmentVerdict.NEUTRAL
    assert results[0].confidence_score == 1.0
    assert not asyncio.iscoroutine(results[0].verdict)


@pytest.mark.asyncio
async def test_nli_10_dependency_injection_route():
    """NLI-10: get_validation_engine dependency injects LocalCrossEncoderNLIProvider."""
    from backend.modules.validation.api.routes import get_validation_engine
    mock_session = AsyncMock()
    engine = get_validation_engine(session=mock_session)

    assert isinstance(engine, ValidationEngine)
    assert isinstance(engine.nli_engine.provider, LocalCrossEncoderNLIProvider)


@pytest.mark.asyncio
async def test_nli_11_deterministic_repeated_inference():
    """NLI-11: Repeated evaluations for the same input produce identical deterministic results."""
    fake_model = FakeCrossEncoderModel(return_scores=[[0.05, 0.90, 0.05]])
    provider = LocalCrossEncoderNLIProvider(model=fake_model)

    r1_v, r1_c = await provider.evaluate_entailment("Premise", "Hypothesis")
    r2_v, r2_c = await provider.evaluate_entailment("Premise", "Hypothesis")

    assert r1_v == r2_v == EntailmentVerdict.ENTAILED
    assert r1_c == r2_c == 0.90


@pytest.mark.asyncio
async def test_nli_12_validation_engine_integration():
    """NLI-12: Full ValidationEngine integration with LocalCrossEncoderNLIProvider."""
    fake_model = FakeCrossEncoderModel(return_scores=[[0.02, 0.95, 0.03]])
    provider = LocalCrossEncoderNLIProvider(model=fake_model)
    nli_engine = NLIValidationEngine(provider)
    mock_repo = AsyncMock()
    engine = ValidationEngine(repository=mock_repo, nli_engine=nli_engine)

    request = ValidationRequestDTO(
        grounded_answer=GroundedAnswerDTO(
            answer_text="The system provides strict encryption [1].",
            citations=[CitationDTO(citation_index=1, excerpt="The system provides strict encryption.", chunk_id="c1", document_id="d1")],
            is_fully_grounded=True,
            correlation_id="corr-val-12",
            evidence_used_count=1,
        ),
        correlation_id="corr-val-12",
        tenant_id="tenant-1",
    )

    result = await engine.validate(request)
    assert result.overall_verdict == EntailmentVerdict.ENTAILED
    assert result.is_valid is True
    assert result.entailment_ratio == 1.0
    assert mock_repo.save_log.called


@pytest.mark.asyncio
async def test_nli_13_model_reuse_lifecycle():
    """NLI-13: Model instance is reused across multiple sequential evaluations."""
    fake_model = FakeCrossEncoderModel(return_scores=[[0.1, 0.8, 0.1]])
    provider = LocalCrossEncoderNLIProvider(model=fake_model)

    await provider.evaluate_entailment("P1", "H1")
    await provider.evaluate_entailment("P2", "H2")
    await provider.evaluate_entailment("P3", "H3")

    assert fake_model.call_count == 3
    assert provider._model is fake_model


@pytest.mark.asyncio
async def test_nli_14_concurrency_safety():
    """NLI-14: Concurrent evaluations execute safely through bounded semaphore."""
    fake_model = FakeCrossEncoderModel(return_scores=[[0.05, 0.90, 0.05]])
    provider = LocalCrossEncoderNLIProvider(model=fake_model, max_concurrency=2)

    tasks = [
        provider.evaluate_entailment(f"Premise {i}", f"Hypothesis {i}")
        for i in range(8)
    ]
    results = await asyncio.gather(*tasks)

    assert len(results) == 8
    for v, c in results:
        assert v == EntailmentVerdict.ENTAILED
        assert c == 0.90


@pytest.mark.asyncio
async def test_nli_15_backward_compatibility_alias():
    """NLI-15: MockCrossEncoderProvider is an alias to HeuristicNLIProvider."""
    assert MockCrossEncoderProvider is HeuristicNLIProvider
    instance = MockCrossEncoderProvider()
    v, c = await instance.evaluate_entailment("The cat sat on the mat.", "The cat was on the mat.")
    assert v == EntailmentVerdict.ENTAILED
