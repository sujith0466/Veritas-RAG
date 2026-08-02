"""Redis Key Namespace and TTL Strategy.

Defines the centralized key format and TTL profiles for all caching operations
to ensure consistency, avoid collisions, and support targeted invalidations.
"""

from enum import Enum
from typing import Any


class TTLProfile(int, Enum):
    """Standardized Time-To-Live (TTL) profiles in seconds."""

    TRANSIENT = 60           # 1 minute
    SHORT = 300              # 5 minutes
    MEDIUM = 3600            # 1 hour
    LONG = 86400             # 24 hours
    MAXIMUM = 604800         # 7 days


class CacheKeyBuilder:
    """Builds strictly formatted Redis keys."""

    VERSION_PREFIX = "rg:v2"

    @classmethod
    def build(
        cls, tenant: str, domain: str, entity: str, entity_id: str | Any
    ) -> str:
        """Construct a Redis key following the strict namespace convention.

        Format: rg:v2:{tenant}:{domain}:{entity}:{id}

        Args:
            tenant: The tenant ID or 'global'.
            domain: The bounded context (e.g., 'auth', 'knowledge', 'chat').
            entity: The specific entity type (e.g., 'user', 'session', 'document').
            entity_id: The unique identifier for the entity.

        Returns:
            Formatted string key.
        """
        # Ensure string conversion
        tenant_str = str(tenant).replace(":", "_")
        domain_str = str(domain).replace(":", "_")
        entity_str = str(entity).replace(":", "_")
        id_str = str(entity_id).replace(":", "_")

        return f"{cls.VERSION_PREFIX}:{tenant_str}:{domain_str}:{entity_str}:{id_str}"
