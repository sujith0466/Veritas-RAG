import structlog

from backend.core.events.base import BaseEvent
from backend.core.events.dispatcher import get_dispatcher
from backend.core.events.types import EventType

logger = structlog.get_logger(__name__)

async def handle_document_changed(event: BaseEvent) -> None:
    """Clear the BM25 sparse index when documents are updated/deleted to force lazy rebuild."""
    tenant_id = getattr(event, "tenant_id", None)
    if not tenant_id and hasattr(event, "payload"):
        tenant_id = getattr(event.payload, "tenant_id", None)

    if not tenant_id:
        logger.warning("No tenant_id in event; cannot invalidate BM25 index", event_type=event.event_type)
        return

    from backend.modules.retrieval.api.dependencies import _bm25_provider
    from backend.modules.retrieval.services.bm25_manager import SparseIndexManager
    manager = SparseIndexManager(sparse_provider=_bm25_provider)
    manager.clear_index(tenant_id)
    logger.info("Invalidated BM25 index due to document change event", tenant_id=tenant_id, event_type=event.event_type)

def register_retrieval_event_handlers() -> None:
    """Register event handlers for the retrieval domain."""
    dispatcher = get_dispatcher()
    dispatcher.subscribe(EventType.VECTORS_INDEXED, handle_document_changed)
    dispatcher.subscribe(EventType.DOCUMENT_DELETED, handle_document_changed)
    logger.info("Registered retrieval event handlers (BM25 invalidation)")
