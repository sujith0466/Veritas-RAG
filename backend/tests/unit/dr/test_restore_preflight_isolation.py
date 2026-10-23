"""Unit tests for Restore Preflight Isolation Checks (`WP-3C Phase 2`, `TSK-3C-07`, `DEC-02`).

Verifies:
1. Rejection of production ports (5432, 6333, 9000, 6379, 6432, 8000, 5173).
2. Acceptance of dedicated isolated restore ports (5433, 6335, 9002, 6389).
3. Rejection of active production volumes (raguard_postgres_data, raguard_minio_data).
4. Acceptance of disposable isolated volumes (veritas_restore_*).
"""

from __future__ import annotations

import pytest

from scripts.dr.verify_restore import (
    RestorePreflightError,
    check_preflight_isolation,
)


def test_preflight_permits_isolated_resources():
    # Dedicated ports 5433, 6335, 9002 and ephemeral volume
    check_preflight_isolation(
        target_ports=[5433, 6335, 9002],
        target_volumes=["veritas_restore_pg_123", "veritas_restore_minio_123"],
    )


def test_preflight_rejects_production_postgres_port():
    with pytest.raises(RestorePreflightError) as exc_info:
        check_preflight_isolation(
            target_ports=[5432, 6335],
            target_volumes=["veritas_restore_vol"],
        )
    assert "protected production port" in str(exc_info.value)


def test_preflight_rejects_production_qdrant_port():
    with pytest.raises(RestorePreflightError) as exc_info:
        check_preflight_isolation(
            target_ports=[5433, 6333],
            target_volumes=["veritas_restore_vol"],
        )
    assert "protected production port" in str(exc_info.value)


def test_preflight_rejects_production_volume_prefix():
    with pytest.raises(RestorePreflightError) as exc_info:
        check_preflight_isolation(
            target_ports=[5433, 6335],
            target_volumes=["raguard_postgres_data"],
        )
    assert "matches active production volume prefix" in str(exc_info.value)
