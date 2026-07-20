"""Repository abstract interfaces."""

from .audit_log_repository import IAuditLogRepository
from .user_repository import IUserRepository

__all__ = ["IAuditLogRepository", "IUserRepository"]
