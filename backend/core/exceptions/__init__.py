"""Exceptions package for RAGuard AI."""

from .auth import (AuthenticationException, AuthorizationException,
                   ExpiredTokenException, InsufficientRoleException,
                   InvalidTokenException)
from .base import (ApplicationException, InfrastructureException,
                   RAGuardException)
from .domain import (BusinessRuleException, ConfidenceThresholdException,
                     ConflictException, IngestionException, NotFoundException,
                     RateLimitException, RetrievalException,
                     RetryBudgetExhaustedException, ValidationException)
from .handlers import get_exception_handlers
from .infrastructure import (CacheConnectionException, CacheException,
                             DatabaseConnectionException, DatabaseException,
                             ExternalServiceException, LLMProviderException,
                             VectorDBConnectionException, VectorDBException)

__all__ = [
    # Base
    "RAGuardException",
    "ApplicationException",
    "InfrastructureException",
    # Auth
    "AuthenticationException",
    "InvalidTokenException",
    "ExpiredTokenException",
    "AuthorizationException",
    "InsufficientRoleException",
    # Domain
    "ValidationException",
    "NotFoundException",
    "ConflictException",
    "RateLimitException",
    "BusinessRuleException",
    "RetrievalException",
    "RetryBudgetExhaustedException",
    "ConfidenceThresholdException",
    "IngestionException",
    # Infrastructure
    "DatabaseException",
    "DatabaseConnectionException",
    "CacheException",
    "CacheConnectionException",
    "VectorDBException",
    "VectorDBConnectionException",
    "ExternalServiceException",
    "LLMProviderException",
    # Handlers
    "get_exception_handlers",
]
