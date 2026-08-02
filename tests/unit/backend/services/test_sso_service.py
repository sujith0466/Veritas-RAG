from unittest.mock import AsyncMock
import uuid

import pytest

from backend.services.sso_service import SSOService, SSOServiceError


@pytest.fixture
def session_mock():
    return AsyncMock()

@pytest.fixture
def dispatcher_mock():
    return AsyncMock()

@pytest.fixture
def service(session_mock, dispatcher_mock):
    return SSOService(session_mock, dispatcher_mock)

@pytest.mark.asyncio
async def test_create_idp_success(service):
    workspace_id = uuid.uuid4()
    data = {
        "name": "Okta",
        "type": "SAML",
        "entity_id_issuer": "issuer",
        "sso_url": "http://sso",
        "attribute_mapping": {"email": "email"},
    }

    idp = await service.create_idp(workspace_id, data)
    assert idp.name == "Okta"
    assert idp.type == "SAML"
    assert idp.jit_enabled is False

    service.session.add.assert_called_once()
    service.session.flush.assert_called_once()
    service.dispatcher.dispatch.assert_called_with("IDP_CREATED", {"idp_id": str(idp.id), "workspace_id": str(workspace_id)})

@pytest.mark.asyncio
async def test_generate_login_request_no_idp(service):
    service.repo.get_active_for_workspace = AsyncMock(return_value=None)
    with pytest.raises(SSOServiceError):
        await service.generate_login_request(uuid.uuid4())
