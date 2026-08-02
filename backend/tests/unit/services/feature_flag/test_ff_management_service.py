"""Unit tests for Feature Flag Management Service."""

from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from backend.models.entities.feature_flag import (
    FeatureFlag,
    FlagCategory,
)
from backend.services.feature_flag.management_service import (
    FeatureFlagManagementService,
)


@pytest.mark.asyncio
async def test_create_feature_flag_success():
    flag_repo = AsyncMock()
    rule_repo = AsyncMock()
    history_repo = AsyncMock()
    workspace_repo = AsyncMock()
    member_repo = AsyncMock()

    service = FeatureFlagManagementService(
        flag_repo, rule_repo, history_repo, workspace_repo, member_repo
    )

    flag_repo.get_by_key.return_value = None
    mock_flag = FeatureFlag(
        id=uuid.uuid4(),
        key="semantic_reranker",
        name="Semantic Reranker",
        category="RAG",
        lifecycle_state="DRAFT",
        flag_type="BOOLEAN",
        default_enabled=False,
        is_killswitch_active=False,
        prerequisite_flag_keys=[],
        default_variant_json={},
        target_environments="production,staging,development",
        version=1,
    )
    flag_repo.create.return_value = mock_flag

    session = AsyncMock()
    actor_id = uuid.uuid4()

    mock_dispatcher = MagicMock()
    mock_dispatcher.publish = AsyncMock()

    with patch("backend.services.feature_flag.management_service.get_dispatcher", return_value=mock_dispatcher):
        created = await service.create_flag(
            session=session,
            actor_id=actor_id,
            key="semantic_reranker",
            name="Semantic Reranker",
            category=FlagCategory.RAG,
        )

    assert created.key == "semantic_reranker"
    assert flag_repo.create.called
    assert history_repo.create.called


@pytest.mark.asyncio
async def test_toggle_killswitch():
    flag_repo = AsyncMock()
    rule_repo = AsyncMock()
    history_repo = AsyncMock()
    workspace_repo = AsyncMock()
    member_repo = AsyncMock()

    service = FeatureFlagManagementService(
        flag_repo, rule_repo, history_repo, workspace_repo, member_repo
    )

    flag_id = uuid.uuid4()
    mock_flag = FeatureFlag(
        id=flag_id,
        key="vector_search_v2",
        name="Vector Search V2",
        category="SYSTEM",
        lifecycle_state="ACTIVE",
        flag_type="BOOLEAN",
        default_enabled=True,
        is_killswitch_active=False,
        prerequisite_flag_keys=[],
        default_variant_json={},
        target_environments="production",
        version=1,
    )
    flag_repo.get_by_key_for_update.return_value = mock_flag
    flag_repo.list_active_flags.return_value = [mock_flag]

    session = AsyncMock()
    actor_id = uuid.uuid4()

    mock_dispatcher = MagicMock()
    mock_dispatcher.publish = AsyncMock()

    with patch("backend.services.feature_flag.management_service.get_dispatcher", return_value=mock_dispatcher), \
         patch("backend.services.feature_flag.management_service.set_active_killswitches_count"):
        updated = await service.toggle_killswitch(
            session=session,
            actor_id=actor_id,
            key="vector_search_v2",
            is_active=True,
            reason="High latency observed in Qdrant cluster",
        )

    assert updated.is_killswitch_active is True
    assert updated.version == 2
    assert history_repo.create.called
