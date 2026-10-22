"""Unit tests for WP-3B Embedding Quota Enforcement, Fatal Error EMB_002, and Idempotency."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.modules.embedding.schemas.errors import (
    EmbeddingErrorCode,
    ErrorSeverity,
    TokenQuotaExceededError,
)
from backend.modules.embedding.services.embedding_service import EmbeddingService


@pytest.mark.asyncio
async def test_initiate_embedding_job_exceeded_quota_raises_emb_002():
    mock_repo = MagicMock()
    mock_repo.get_unembedded_chunks = AsyncMock(return_value=[MagicMock(), MagicMock()])
    mock_repo.get_tenant_metrics = AsyncMock(return_value={"total_tokens_consumed": 15000})

    service = EmbeddingService(repository=mock_repo)

    # With max_token_quota set to 10,000, and used at 15,000 -> must raise TokenQuotaExceededError (EMB_002)
    with pytest.raises(TokenQuotaExceededError) as exc_info:
        await service.initiate_embedding_job(
            tenant_id="tenant-123",
            document_id=uuid.uuid4(),
            document_version_id=uuid.uuid4(),
            max_token_quota=10000,
        )

    err = exc_info.value
    assert err.code == EmbeddingErrorCode.EMB_002
    assert err.severity == ErrorSeverity.FATAL


@pytest.mark.asyncio
async def test_initiate_embedding_job_within_quota_succeeds():
    mock_repo = MagicMock()
    mock_repo.get_unembedded_chunks = AsyncMock(return_value=[MagicMock()])
    mock_repo.get_tenant_metrics = AsyncMock(return_value={"total_tokens_consumed": 2000})
    created_mock_job = MagicMock(id=uuid.uuid4())
    mock_repo.create_job = AsyncMock(return_value=created_mock_job)
    mock_repo.session = MagicMock()
    mock_repo.session.commit = AsyncMock()

    service = EmbeddingService(repository=mock_repo)

    job = await service.initiate_embedding_job(
        tenant_id="tenant-123",
        document_id=uuid.uuid4(),
        document_version_id=uuid.uuid4(),
        max_token_quota=10000,
    )
    assert job == created_mock_job


@pytest.mark.asyncio
async def test_process_embedding_batch_precheck_quota_exhausted_raises_fatal_emb_002():
    mock_repo = MagicMock()
    mock_job = MagicMock()
    mock_job.id = uuid.uuid4()
    mock_job.provider = "openai"
    mock_job.model_name = "text-embedding-3-small"
    mock_job.document_version_id = uuid.uuid4()
    mock_repo.get_job_by_id_and_tenant = AsyncMock(return_value=mock_job)
    mock_repo.update_job_progress = AsyncMock()
    mock_chunk = MagicMock(content="Sample chunk text", content_hash="hash123")
    mock_repo.get_unembedded_chunks = AsyncMock(return_value=[mock_chunk])
    mock_repo.get_existing_embeddings_by_hashes = AsyncMock(return_value={})
    mock_repo.session = MagicMock()

    service = EmbeddingService(repository=mock_repo)

    # Mock QuotaGovernor to report quota exceeded
    target_ws = str(uuid.uuid4())
    with patch("backend.modules.analytics.services.quota.QuotaGovernor.check_quota", new_callable=AsyncMock) as mock_cq:
        mock_cq.return_value = (True, 10_000_000, 10_000_000, True)  # is_exceeded=True, hard=True

        with pytest.raises(TokenQuotaExceededError) as exc_info:
            await service.process_embedding_batch(
                job_id=mock_job.id,
                tenant_id=target_ws,
                batch_size=10,
            )

        err = exc_info.value
        assert err.code == EmbeddingErrorCode.EMB_002
        assert err.severity == ErrorSeverity.FATAL


@pytest.mark.asyncio
async def test_process_embedding_batch_records_token_usage_deduplicated():
    mock_repo = MagicMock()
    mock_job = MagicMock()
    mock_job.id = uuid.uuid4()
    mock_job.provider = "openai"
    mock_job.model_name = "text-embedding-3-small"
    mock_job.document_version_id = uuid.uuid4()
    mock_repo.get_job_by_id_and_tenant = AsyncMock(return_value=mock_job)
    mock_repo.update_job_progress = AsyncMock()
    mock_chunk = MagicMock(id=uuid.uuid4(), content="Sample chunk text", content_hash="hash123")
    mock_repo.get_unembedded_chunks = AsyncMock(side_effect=[[mock_chunk], []])
    mock_repo.get_existing_embeddings_by_hashes = AsyncMock(return_value={})
    mock_repo.bulk_insert_chunk_embeddings = AsyncMock()
    mock_repo.mark_chunks_as_embedded = AsyncMock()
    mock_repo.session = MagicMock()

    service = EmbeddingService(repository=mock_repo)

    target_ws = str(uuid.uuid4())
    with patch("backend.modules.analytics.services.quota.QuotaGovernor.check_quota", new_callable=AsyncMock) as mock_cq, \
         patch("backend.modules.analytics.services.quota.QuotaGovernor.record_token_usage", new_callable=AsyncMock) as mock_rec, \
         patch("backend.modules.embedding.providers.manager.EmbeddingManager.vectorize_batch", new_callable=AsyncMock) as mock_vec:

        mock_cq.return_value = (False, 1000, 10_000_000, True)
        mock_vec.return_value = MagicMock(
            tokens_consumed=150,
            embeddings=[[0.1] * 1536],
            provider_metadata={},
        )
        mock_rec.return_value = (MagicMock(), True)

        await service.process_embedding_batch(
            job_id=mock_job.id,
            tenant_id=target_ws,
            batch_size=10,
        )

        # Confirm token usage was recorded with deterministic correlation_id
        assert mock_rec.called
        call_kwargs = mock_rec.call_args.kwargs
        assert call_kwargs["prompt_tokens"] == 150
        assert call_kwargs["completion_tokens"] == 0
        assert str(mock_job.id) in call_kwargs["correlation_id"]
        assert "emb:" in call_kwargs["correlation_id"]
