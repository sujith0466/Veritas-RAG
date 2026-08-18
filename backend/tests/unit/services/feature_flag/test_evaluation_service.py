"""Unit tests for Feature Flag Evaluation Engine (7-step resolution pipeline)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from backend.models.entities.feature_flag import FeatureFlag
from backend.models.entities.feature_flag_workspace_rule import FeatureFlagWorkspaceRule
from backend.services.feature_flag.evaluation_service import (
    EvaluationContext,
    FeatureFlagEvaluationService,
    _murmur3_32_seedless,
    is_entity_in_rollout,
    validate_no_circular_dependencies,
)


def test_murmur3_rollout_deterministic():
    flag_key = "new_rag_pipeline"
    entity_id_1 = "user-123"
    entity_id_2 = "user-456"

    # Same input produces identical hash
    hash1 = _murmur3_32_seedless(f"{flag_key}:{entity_id_1}".encode())
    hash2 = _murmur3_32_seedless(f"{flag_key}:{entity_id_1}".encode())
    assert hash1 == hash2

    # 100% rollout is always True, 0% is always False
    assert is_entity_in_rollout(flag_key, entity_id_1, 100) is True
    assert is_entity_in_rollout(flag_key, entity_id_1, 0) is False


def test_circular_dependency_detection():
    # Valid graph: A -> B -> C (DAG)
    graph = {
        "A": ["B"],
        "B": ["C"],
        "C": [],
    }
    validate_no_circular_dependencies("A", ["B"], graph)

    # Cycle: A -> B -> A
    cycle_graph = {
        "A": ["B"],
        "B": ["A"],
    }
    with pytest.raises(ValueError, match="Circular prerequisite dependency detected"):
        validate_no_circular_dependencies("A", ["B"], cycle_graph)


@pytest.mark.asyncio
async def test_evaluation_killswitch_priority():
    flag_repo = AsyncMock()
    rule_repo = AsyncMock()
    service = FeatureFlagEvaluationService(flag_repo, rule_repo)

    flag_id = uuid.uuid4()
    mock_flag = FeatureFlag(
        id=flag_id,
        key="critical_feature",
        name="Critical Feature",
        lifecycle_state="ACTIVE",
        default_enabled=True,
        is_killswitch_active=True,  # Killswitch is engaged!
        prerequisite_flag_keys=[],
        default_variant_json={"v": 1},
        target_environments="production",
    )
    flag_repo.get_by_key.return_value = mock_flag
    rule_repo.get_by_flag_and_workspace.return_value = None

    context = EvaluationContext(workspace_id=uuid.uuid4())
    session = AsyncMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.delete = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    service.invalidate_local_cache()
    result = await service.evaluate_flag(session, "critical_feature", context)

    assert result.is_enabled is False
    assert result.reason == "KILLSWITCH"


@pytest.mark.asyncio
async def test_evaluation_workspace_override_disabled():
    flag_repo = AsyncMock()
    rule_repo = AsyncMock()
    service = FeatureFlagEvaluationService(flag_repo, rule_repo)

    flag_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    mock_flag = FeatureFlag(
        id=flag_id,
        key="beta_feature",
        name="Beta Feature",
        lifecycle_state="ACTIVE",
        default_enabled=True,
        is_killswitch_active=False,
        prerequisite_flag_keys=[],
        default_variant_json={},
        target_environments="production",
    )
    mock_rule = FeatureFlagWorkspaceRule(
        id=uuid.uuid4(),
        flag_id=flag_id,
        workspace_id=workspace_id,
        is_enabled=False,  # Workspace admin explicitly disabled this flag
        rollout_percentage=100,
        targeting_conditions_json=[],
        custom_variant_json={},
    )
    flag_repo.get_by_key.return_value = mock_flag
    rule_repo.get_by_flag_and_workspace.return_value = mock_rule

    context = EvaluationContext(workspace_id=workspace_id)
    session = AsyncMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.delete = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    service.invalidate_local_cache()
    result = await service.evaluate_flag(session, "beta_feature", context)

    assert result.is_enabled is False
    assert result.reason == "WORKSPACE_OVERRIDE_DISABLED"


@pytest.mark.asyncio
async def test_evaluation_user_targeting_match():
    flag_repo = AsyncMock()
    rule_repo = AsyncMock()
    service = FeatureFlagEvaluationService(flag_repo, rule_repo)

    flag_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    target_user_id = uuid.uuid4()

    mock_flag = FeatureFlag(
        id=flag_id,
        key="targeted_feature",
        name="Targeted Feature",
        lifecycle_state="ACTIVE",
        default_enabled=False,
        is_killswitch_active=False,
        prerequisite_flag_keys=[],
        default_variant_json={},
        target_environments="production",
    )
    mock_rule = FeatureFlagWorkspaceRule(
        id=uuid.uuid4(),
        flag_id=flag_id,
        workspace_id=workspace_id,
        is_enabled=True,
        rollout_percentage=0,  # 0% rollout, but targeting condition matches!
        targeting_conditions_json=[
            {"type": "USER_ID", "values": [str(target_user_id)]}
        ],
        custom_variant_json={"variant": "vip"},
    )
    flag_repo.get_by_key.return_value = mock_flag
    rule_repo.get_by_flag_and_workspace.return_value = mock_rule

    context = EvaluationContext(workspace_id=workspace_id, user_id=target_user_id)
    session = AsyncMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.delete = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    service.invalidate_local_cache()
    result = await service.evaluate_flag(session, "targeted_feature", context)

    assert result.is_enabled is True
    assert result.reason == "USER_TARGETING_MATCH"
    assert result.variant == {"variant": "vip"}


@pytest.mark.asyncio
async def test_evaluation_role_targeting_match():
    flag_repo = AsyncMock()
    rule_repo = AsyncMock()
    service = FeatureFlagEvaluationService(flag_repo, rule_repo)

    flag_id = uuid.uuid4()
    workspace_id = uuid.uuid4()

    mock_flag = FeatureFlag(
        id=flag_id,
        key="admin_only_feature",
        name="Admin Feature",
        lifecycle_state="ACTIVE",
        default_enabled=False,
        is_killswitch_active=False,
        prerequisite_flag_keys=[],
        default_variant_json={},
        target_environments="production",
    )
    mock_rule = FeatureFlagWorkspaceRule(
        id=uuid.uuid4(),
        flag_id=flag_id,
        workspace_id=workspace_id,
        is_enabled=True,
        rollout_percentage=0,
        targeting_conditions_json=[
            {"type": "ROLE", "values": ["ADMIN", "OWNER"]}
        ],
        custom_variant_json={},
    )
    flag_repo.get_by_key.return_value = mock_flag
    rule_repo.get_by_flag_and_workspace.return_value = mock_rule

    context = EvaluationContext(workspace_id=workspace_id, workspace_role="ADMIN")
    session = AsyncMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.delete = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    service.invalidate_local_cache()
    result = await service.evaluate_flag(session, "admin_only_feature", context)

    assert result.is_enabled is True
    assert result.reason == "ROLE_TARGETING_MATCH"


@pytest.mark.asyncio
async def test_evaluation_date_window():
    flag_repo = AsyncMock()
    rule_repo = AsyncMock()
    service = FeatureFlagEvaluationService(flag_repo, rule_repo)

    flag_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    now = datetime.now(UTC)

    # Future window -> should fail
    mock_flag = FeatureFlag(
        id=flag_id,
        key="scheduled_feature",
        name="Scheduled Feature",
        lifecycle_state="ACTIVE",
        default_enabled=False,
        is_killswitch_active=False,
        prerequisite_flag_keys=[],
        default_variant_json={},
        target_environments="production",
    )
    mock_rule = FeatureFlagWorkspaceRule(
        id=uuid.uuid4(),
        flag_id=flag_id,
        workspace_id=workspace_id,
        is_enabled=True,
        rollout_percentage=100,
        activation_start_at=now + timedelta(days=1),
        activation_end_at=now + timedelta(days=5),
        targeting_conditions_json=[],
        custom_variant_json={},
    )
    flag_repo.get_by_key.return_value = mock_flag
    rule_repo.get_by_flag_and_workspace.return_value = mock_rule

    context = EvaluationContext(workspace_id=workspace_id)
    session = AsyncMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.delete = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    service.invalidate_local_cache()
    result = await service.evaluate_flag(session, "scheduled_feature", context)

    assert result.is_enabled is False
    assert result.reason == "BEFORE_DATE_WINDOW"
