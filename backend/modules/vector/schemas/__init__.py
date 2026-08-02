"""Vector storage error taxonomy and schemas package."""

from backend.modules.vector.schemas.errors import (
                                                   CollectionNotFoundError,
                                                   DimensionMismatchError,
                                                   ErrorSeverity,
                                                   IndexSyncTimeoutError,
                                                   InvalidPayloadSchemaError,
                                                   QdrantConnectionError,
                                                   VectorDomainException,
                                                   VectorErrorCode,
                                                   get_error_severity,
)
from backend.modules.vector.schemas.payload import (
                                                   CollectionConfigDTO,
                                                   CollectionDetailDTO,
                                                   CollectionSummaryDTO,
                                                   PurgeSummaryDTO,
                                                   QdrantClusterHealthDTO,
                                                   VectorBatchRequestDTO,
                                                   VectorIndexMetadataDTO,
                                                   VectorPointDTO,
                                                   VectorSyncRequestDTO,
)

__all__ = [
    "CollectionConfigDTO",
    "CollectionDetailDTO",
    "CollectionNotFoundError",
    "CollectionSummaryDTO",
    "DimensionMismatchError",
    "ErrorSeverity",
    "IndexSyncTimeoutError",
    "InvalidPayloadSchemaError",
    "PurgeSummaryDTO",
    "QdrantClusterHealthDTO",
    "QdrantConnectionError",
    "VectorBatchRequestDTO",
    "VectorDomainException",
    "VectorErrorCode",
    "VectorIndexMetadataDTO",
    "VectorPointDTO",
    "VectorSyncRequestDTO",
    "get_error_severity",
]
