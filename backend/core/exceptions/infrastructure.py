"""Infrastructure exceptions for downstream service failures."""

from http import HTTPStatus

from .base import InfrastructureException


class DatabaseException(InfrastructureException):
    """503 — PostgreSQL connection or query failure."""

    error_code = "DB_001"
    default_message = "Database operation failed"
    http_status = HTTPStatus.SERVICE_UNAVAILABLE


class DatabaseConnectionException(DatabaseException):
    """503 — Cannot establish a connection to the database."""

    error_code = "DB_002"
    default_message = "Database connection unavailable"


class CacheException(InfrastructureException):
    """503 — Redis operation failure."""

    error_code = "CACHE_001"
    default_message = "Cache operation failed"
    http_status = HTTPStatus.SERVICE_UNAVAILABLE


class CacheConnectionException(CacheException):
    """503 — Cannot connect to Redis."""

    error_code = "CACHE_002"
    default_message = "Cache connection unavailable"


class VectorDBException(InfrastructureException):
    """503 — Qdrant operation failure."""

    error_code = "VDB_001"
    default_message = "Vector database operation failed"
    http_status = HTTPStatus.SERVICE_UNAVAILABLE


class VectorDBConnectionException(VectorDBException):
    """503 — Cannot connect to Qdrant."""

    error_code = "VDB_002"
    default_message = "Vector database connection unavailable"


class ExternalServiceException(InfrastructureException):
    """502 — External API (e.g., Gemini, embedding provider) returned an error."""

    error_code = "EXT_001"
    default_message = "External service request failed"
    http_status = HTTPStatus.BAD_GATEWAY


class LLMProviderException(ExternalServiceException):
    """502 — LLM provider (Gemini) returned an error or timed out."""

    error_code = "EXT_002"
    default_message = "LLM provider request failed"
