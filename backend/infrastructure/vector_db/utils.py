"""Vector DB utilities and formatters."""

from backend.core.config import get_settings


class CollectionNameBuilder:
    """Centralized builder for vector database collection names."""

    @classmethod
    def build(cls, tenant_id: str) -> str:
        """Generate a tenant-scoped collection name.
        
        Format: {prefix}_{tenant_id}
        """
        prefix = get_settings().qdrant.collection_prefix
        # Ensure string conversion and remove characters that might break Qdrant
        tenant_str = str(tenant_id).replace("-", "_").replace(":", "_").lower()
        return f"{prefix}_{tenant_str}"
