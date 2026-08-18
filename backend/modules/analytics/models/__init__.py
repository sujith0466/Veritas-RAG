"""ORM models for the Query Analytics module."""

from .query_analytics import QueryAnalyticsRecord
from .tenant_quota import TenantQuotaORM

__all__ = ["QueryAnalyticsRecord", "TenantQuotaORM"]
