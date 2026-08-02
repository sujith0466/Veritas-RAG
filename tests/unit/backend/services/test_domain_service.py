from unittest.mock import AsyncMock
import uuid

import pytest

from backend.models.entities.workspace_domain import DomainCooldown
from backend.services.domain_service import (
    DomainAlreadyVerifiedError,
    DomainCooldownError,
    WorkspaceDomainService,
)


@pytest.fixture
def session_mock():
    return AsyncMock()

@pytest.fixture
def dispatcher_mock():
    return AsyncMock()

@pytest.fixture
def service(session_mock, dispatcher_mock):
    return WorkspaceDomainService(session_mock, dispatcher_mock)

@pytest.mark.asyncio
async def test_add_domain_success(service):
    service.repo.is_verified_globally = AsyncMock(return_value=False)
    service.repo.get_cooldown = AsyncMock(return_value=None)

    workspace_id = uuid.uuid4()
    domain, token = await service.add_domain(workspace_id, "Example.COM")

    assert domain.domain_name == "example.com"
    assert domain.workspace_id == workspace_id
    assert domain.status == "PENDING"
    assert token is not None
    assert domain.verification_token_hash is not None

@pytest.mark.asyncio
async def test_add_domain_idn_normalization(service):
    service.repo.is_verified_globally = AsyncMock(return_value=False)
    service.repo.get_cooldown = AsyncMock(return_value=None)

    workspace_id = uuid.uuid4()
    domain, token = await service.add_domain(workspace_id, "münchen.de")

    assert domain.domain_name == "xn--mnchen-3ya.de"

@pytest.mark.asyncio
async def test_add_domain_duplicate_verified(service):
    service.repo.is_verified_globally = AsyncMock(return_value=True)

    with pytest.raises(DomainAlreadyVerifiedError):
        await service.add_domain(uuid.uuid4(), "acme.com")

@pytest.mark.asyncio
async def test_add_domain_in_cooldown(service):
    service.repo.is_verified_globally = AsyncMock(return_value=False)
    service.repo.get_cooldown = AsyncMock(return_value=DomainCooldown())

    with pytest.raises(DomainCooldownError):
        await service.add_domain(uuid.uuid4(), "acme.com")
