"""Unit tests for Phase 2 Milestone 2: Embedding Pipeline (Milestone A - Foundation).

Verifies base interfaces, exact domain error taxonomy, Pydantic v2 DTO validation,
provider factory catalog and placeholder behavior, and configuration loading.
"""

from http import HTTPStatus
import uuid

from pydantic import ValidationError
import pytest

from backend.core.config import get_settings
from backend.modules.embedding.providers.base import BaseEmbeddingProvider, EmbeddingBatchResult
from backend.modules.embedding.providers.factory import EmbeddingProviderFactory, register_provider
from backend.modules.embedding.schemas.embedding_dto import (
    EmbeddingJobDTO,
    EmbeddingProcessRequestDTO,
)
from backend.modules.embedding.schemas.errors import (
    EmbeddingDomainException,
    EmbeddingErrorCode,
    ErrorSeverity,
    InvalidInputError,
    ProviderAuthenticationError,
    ProviderTimeoutError,
    RateLimitExceededError,
    TokenQuotaExceededError,
    get_error_severity,
)


class DummyProvider(BaseEmbeddingProvider):
    """Mock implementation of BaseEmbeddingProvider for interface testing."""

    def __init__(self, model_name: str | None = None, api_key: str | None = None) -> None:
        self._model = model_name or "dummy-1024"

    @property
    def dimension(self) -> int:
        return 1024

    @property
    def model_name(self) -> str:
        return self._model

    async def embed_documents(self, texts: list[str]) -> EmbeddingBatchResult:
        vectors = [[0.1] * 1024 for _ in texts]
        return EmbeddingBatchResult(embeddings=vectors, tokens_consumed=len(texts) * 5)

    async def embed_query(self, text: str) -> list[float]:
        return [0.1] * 1024


@pytest.mark.asyncio
async def test_base_provider_interface() -> None:
    """Verify concrete subclassing of BaseEmbeddingProvider and contract fulfillment."""
    provider = DummyProvider()
    assert provider.dimension == 1024
    assert provider.model_name == "dummy-1024"

    res = await provider.embed_documents(["hello", "world"])
    assert isinstance(res, EmbeddingBatchResult)
    assert len(res.embeddings) == 2
    assert len(res.embeddings[0]) == 1024
    assert res.tokens_consumed == 10

    query_vec = await provider.embed_query("test query")
    assert len(query_vec) == 1024


def test_error_taxonomy_and_severities() -> None:
    """Verify exact domain error codes, severities, and HTTP status code mappings."""
    assert get_error_severity("EMB_001") == ErrorSeverity.FATAL
    assert get_error_severity("EMB_002") == ErrorSeverity.FATAL
    assert get_error_severity("EMB_003") == ErrorSeverity.RECOVERABLE
    assert get_error_severity("EMB_004") == ErrorSeverity.RECOVERABLE
    assert get_error_severity("EMB_005") == ErrorSeverity.FATAL

    e1 = InvalidInputError("Invalid chunk batch")
    assert e1.code == EmbeddingErrorCode.EMB_001
    assert e1.severity == ErrorSeverity.FATAL
    assert e1.http_status == HTTPStatus.BAD_REQUEST

    e2 = TokenQuotaExceededError("Monthly quota exceeded")
    assert e2.code == EmbeddingErrorCode.EMB_002
    assert e2.severity == ErrorSeverity.FATAL
    assert e2.http_status == HTTPStatus.TOO_MANY_REQUESTS

    e3 = RateLimitExceededError("HTTP 429 rate limit hit")
    assert e3.code == EmbeddingErrorCode.EMB_003
    assert e3.severity == ErrorSeverity.RECOVERABLE
    assert e3.http_status == HTTPStatus.TOO_MANY_REQUESTS

    e4 = ProviderTimeoutError("Gateway timeout")
    assert e4.code == EmbeddingErrorCode.EMB_004
    assert e4.severity == ErrorSeverity.RECOVERABLE
    assert e4.http_status == HTTPStatus.GATEWAY_TIMEOUT

    e5 = ProviderAuthenticationError("Invalid API key")
    assert e5.code == EmbeddingErrorCode.EMB_005
    assert e5.severity == ErrorSeverity.FATAL
    assert e5.http_status == HTTPStatus.UNAUTHORIZED


def test_embedding_dto_validation() -> None:
    """Verify Pydantic v2 validation and property calculations across domain DTOs."""
    req = EmbeddingProcessRequestDTO(
        document_id=uuid.uuid4(),
        document_version_id=uuid.uuid4(),
        provider="openai",
        model_name="text-embedding-3-large",
        batch_size=50,
    )
    assert req.batch_size == 50

    with pytest.raises(ValidationError):
        # batch_size out of bounds (> 500)
        EmbeddingProcessRequestDTO(document_id=uuid.uuid4(), document_version_id=uuid.uuid4(), batch_size=600)

    job = EmbeddingJobDTO(
        job_id=uuid.uuid4(),
        tenant_id="tenant-1",
        document_id=uuid.uuid4(),
        document_version_id=uuid.uuid4(),
        status="PROCESSING",
        provider="openai",
        model_name="text-embedding-3-large",
        total_chunks=100,
        processed_chunks=45,
    )
    assert job.progress_percentage == 45.0

    job_done = job.model_copy(update={"processed_chunks": 100, "status": "COMPLETED"})
    assert job_done.progress_percentage == 100.0


def test_provider_factory_catalog_and_lookup() -> None:
    """Verify provider factory catalog generation and error handling when unregistered."""
    catalog = EmbeddingProviderFactory.list_available_providers()
    assert len(catalog) >= 3
    provider_codes = {p.provider for p in catalog}
    assert {"openai", "cohere", "local"}.issubset(provider_codes)

    # In Milestone A, concrete providers aren't registered yet.
    # Requesting an unregistered provider code raises EMB_001.
    with pytest.raises(EmbeddingDomainException) as exc_info:
        EmbeddingProviderFactory.get_provider("unregistered_dummy")
    assert exc_info.value.code == EmbeddingErrorCode.EMB_001

    # Test registration of our dummy provider and resolution
    register_provider("dummy", DummyProvider)
    instance = EmbeddingProviderFactory.get_provider("dummy", model_name="dummy-2048")
    assert isinstance(instance, BaseEmbeddingProvider)
    assert instance.model_name == "dummy-2048"


def test_embedding_configuration_loading(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify settings initialization includes embedding configuration."""
    monkeypatch.setenv("DEFAULT_EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("EMBEDDING_BATCH_SIZE", "100")
    monkeypatch.setenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")
    get_settings.cache_clear()

    settings = get_settings()
    assert hasattr(settings, "embeddings")
    assert settings.embeddings.default_provider == "openai"
    assert settings.embeddings.batch_size == 100
    assert settings.embeddings.openai_model == "text-embedding-3-large"
