import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
from backend.modules.vector.services.vector_service import VectorStorageService

pytestmark = pytest.mark.asyncio

@pytest.fixture
def mock_session():
    return AsyncMock()

@pytest.fixture
def service(mock_session):
    with patch("backend.modules.vector.services.vector_service.VectorProviderFactory") as factory_cls, \
         patch("backend.modules.vector.services.vector_service.VectorMetadataRepository") as repo_cls, \
         patch("backend.modules.vector.services.vector_service.get_dispatcher") as get_dispatcher_mock:
        
        mock_provider = AsyncMock()
        factory_cls.get_provider.return_value = mock_provider
        repo_cls.return_value = AsyncMock()
        mock_execute = MagicMock()
        mock_scalars = MagicMock()
        mock_rec = MagicMock()
        mock_rec.id = uuid.uuid4()
        mock_rec.collection_name = "col_tenant-1_default"
        # Make the mock act as a string when iterated or used as col name
        mock_rec.__str__.return_value = "col_tenant-1_default"
        mock_scalars.all.return_value = [mock_rec]
        mock_execute.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_execute
        
        yield VectorStorageService(session=mock_session)

async def test_remove_archived_document_vectors(service):
    doc_id = str(uuid.uuid4())
    tenant_id = "tenant-1"
    
    # Mock finding collections
    service.provider.list_collections = AsyncMock(return_value=[f"col_{tenant_id}_1", "col_other_1"])
    service.provider.delete_points_by_filter.return_value = 5
    
    deleted_count = await service.remove_archived_document_vectors(doc_id, tenant_id)
    
    assert deleted_count == 5
    service.provider.delete_points_by_filter.assert_called_once()
    
async def test_cleanup_old_versions_vectors(service, mock_session):
    doc_id = uuid.uuid4()
    current_ver = uuid.uuid4()
    tenant_id = "tenant-1"
    col_name = "test_collection"
    
    # Mock old versions returned by repo
    service.repo.get_old_versions_for_document = AsyncMock(return_value=[uuid.uuid4(), uuid.uuid4()])
    service.provider.delete_points_by_filter.return_value = 5
    service.repo.mark_vectors_deleted = AsyncMock()
    
    # Setup two mock metadata records
    mock_rec1 = MagicMock()
    mock_rec1.id = uuid.uuid4()
    mock_rec1.collection_name = "col_1"
    mock_rec1.document_version_id = uuid.uuid4()
    
    mock_rec2 = MagicMock()
    mock_rec2.id = uuid.uuid4()
    mock_rec2.collection_name = "col_2"
    mock_rec2.document_version_id = uuid.uuid4()
    
    mock_execute = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_rec1, mock_rec2]
    mock_execute.scalars.return_value = mock_scalars
    mock_session.execute.return_value = mock_execute
    
    await service.cleanup_old_versions_vectors(doc_id, current_ver, tenant_id, col_name)
    
    assert service.provider.delete_points_by_filter.call_count == 2
    assert service.repo.update_sync_status.call_count == 2
