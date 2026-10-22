"""Unit tests for WP-3B Quota Alert Worker, 80%/95% thresholds, and duplicate suppression."""

from datetime import date, datetime, timezone
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.modules.analytics.workers.quota_alerts import (
    ACTION_CRITICAL_95,
    ACTION_WARNING_80,
    check_workspace_quota_alerts,
)


@pytest.mark.asyncio
async def test_quota_alert_boundaries():
    """Verify 79% (no alert), 80% (warning_80), and 95% (critical_95)."""
    ws1 = MagicMock(id=uuid.uuid4(), name="Workspace 79%", is_deleted=False)
    ws2 = MagicMock(id=uuid.uuid4(), name="Workspace 80%", is_deleted=False)
    ws3 = MagicMock(id=uuid.uuid4(), name="Workspace 95%", is_deleted=False)

    mock_session = MagicMock()
    # Mock workspace query
    mock_ws_result = MagicMock()
    mock_ws_result.scalars.return_value.all.return_value = [ws1, ws2, ws3]

    # Mock audit log duplicate check queries (return None meaning no duplicate exists)
    mock_dup_result = MagicMock()
    mock_dup_result.scalar_one_or_none.return_value = None

    mock_session.execute = AsyncMock(side_effect=[
        mock_ws_result,  # workspace query
        mock_dup_result,  # ws2 dup check
        mock_dup_result,  # ws3 dup check
    ])
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    limit = 10_000_000

    def mock_usage(workspace_id=None, session=None, period_start=None):
        if workspace_id == ws1.id:
            return 7_900_000  # 79%
        elif workspace_id == ws2.id:
            return 8_000_000  # 80%
        elif workspace_id == ws3.id:
            return 9_500_000  # 95%
        return 0

    with patch("backend.modules.analytics.services.quota.QuotaGovernor.get_quota_settings", new_callable=AsyncMock) as mock_qs, \
         patch("backend.modules.analytics.services.quota.QuotaGovernor.get_durable_usage", new_callable=AsyncMock) as mock_gu:

        mock_qs.return_value = MagicMock(monthly_token_limit=limit)
        mock_gu.side_effect = mock_usage

        alerts = await check_workspace_quota_alerts(mock_session, as_of_date=date(2026, 10, 22))

        # ws1 at 79% should NOT generate alert
        # ws2 at 80% should generate warning_80
        # ws3 at 95% should generate critical_95
        assert len(alerts) == 2

        actions_recorded = [call.args[0].action for call in mock_session.add.call_args_list]
        assert ACTION_WARNING_80 in actions_recorded
        assert ACTION_CRITICAL_95 in actions_recorded

        details = [call.args[0].details for call in mock_session.add.call_args_list]
        ws_ids_alerted = [d["workspace_id"] for d in details]
        assert str(ws1.id) not in ws_ids_alerted
        assert str(ws2.id) in ws_ids_alerted
        assert str(ws3.id) in ws_ids_alerted


@pytest.mark.asyncio
async def test_quota_alert_duplicate_suppression_on_repeated_runs():
    """Verify that repeated runs during the same billing period do NOT produce duplicate alerts."""
    ws = MagicMock(id=uuid.uuid4(), name="Workspace High Usage", is_deleted=False)

    mock_session = MagicMock()
    mock_ws_result = MagicMock()
    mock_ws_result.scalars.return_value.all.return_value = [ws]

    # Duplicate check query returns an existing audit log id -> alert should be suppressed
    mock_dup_result = MagicMock()
    mock_dup_result.scalar_one_or_none.return_value = uuid.uuid4()

    mock_session.execute = AsyncMock(side_effect=[
        mock_ws_result,
        mock_dup_result,
    ])
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    with patch("backend.modules.analytics.services.quota.QuotaGovernor.get_quota_settings", new_callable=AsyncMock) as mock_qs, \
         patch("backend.modules.analytics.services.quota.QuotaGovernor.get_durable_usage", new_callable=AsyncMock) as mock_gu:

        mock_qs.return_value = MagicMock(monthly_token_limit=10_000_000)
        mock_gu.return_value = 8_500_000  # 85%

        alerts = await check_workspace_quota_alerts(mock_session, as_of_date=date(2026, 10, 22))

        # Alert was already logged this period, so 0 new alerts should be added
        assert len(alerts) == 0
        assert mock_session.add.call_count == 0
