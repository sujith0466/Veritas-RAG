"""Schemas and DTOs for the hybrid retrieval engine."""

from backend.modules.retrieval.schemas.errors import (
    ERROR_SEVERITY_MAP, ErrorSeverity, FusionPipelineError, InvalidQueryError,
    RerankerTimeoutError, RetrievalDomainException, RetrievalErrorCode,
    SparseIndexNotFoundError, VectorStoreUnavailableError, get_error_severity)
from backend.modules.retrieval.schemas.retrieval_dto import (
    CandidatePointDTO, RankedEvidenceDTO, RetrievalMetricsDTO,
    RetrievalQueryLogDTO, RetrievalResultDTO, RetrievalStageBreakdownDTO,
    SearchRequestDTO, SearchSandboxResponseDTO)

__all__ = [
    "ERROR_SEVERITY_MAP",
    "ErrorSeverity",
    "FusionPipelineError",
    "InvalidQueryError",
    "RerankerTimeoutError",
    "RetrievalDomainException",
    "RetrievalErrorCode",
    "SparseIndexNotFoundError",
    "VectorStoreUnavailableError",
    "get_error_severity",
    "CandidatePointDTO",
    "RankedEvidenceDTO",
    "RetrievalMetricsDTO",
    "RetrievalQueryLogDTO",
    "RetrievalResultDTO",
    "RetrievalStageBreakdownDTO",
    "SearchRequestDTO",
    "SearchSandboxResponseDTO",
]
