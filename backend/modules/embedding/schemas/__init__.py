"""Embedding Pipeline domain schemas and error taxonomies."""

from .embedding_dto import (EmbeddingJobDetailDTO, EmbeddingJobDTO,
                            EmbeddingMetricsDTO, EmbeddingProcessRequestDTO,
                            PaginatedJobResponse, ProviderInfoDTO,
                            ProviderModelInfoDTO)
from .errors import (EmbeddingDomainException, EmbeddingErrorCode,
                     ErrorSeverity, InvalidInputError,
                     ProviderAuthenticationError, ProviderRateLimitError,
                     ProviderTimeoutError, RateLimitExceededError,
                     TokenQuotaExceededError)

__all__ = [
    "EmbeddingJobDetailDTO",
    "EmbeddingJobDTO",
    "EmbeddingMetricsDTO",
    "EmbeddingProcessRequestDTO",
    "PaginatedJobResponse",
    "ProviderInfoDTO",
    "ProviderModelInfoDTO",
    "EmbeddingDomainException",
    "EmbeddingErrorCode",
    "ErrorSeverity",
    "InvalidInputError",
    "ProviderAuthenticationError",
    "ProviderRateLimitError",
    "ProviderTimeoutError",
    "RateLimitExceededError",
    "TokenQuotaExceededError",
]
