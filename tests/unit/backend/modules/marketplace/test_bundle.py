import pytest

from backend.modules.marketplace.services.bundle import BundleInstaller, BundleService
from backend.modules.marketplace.services.registry import MarketplaceRegistry


def test_bundle_service_and_installer():
    service = BundleService()
    installer = BundleInstaller()
    registry = MarketplaceRegistry()

    bundle = service.export_tenant_config("t1", "b1", "1.0.0")
    assert bundle.bundle_id == "b1"
    assert bundle.signature_hash is not None

    registry.publish_bundle(bundle)
    fetched = registry.get_bundle("b1")
    assert fetched is not None

    result = installer.install_bundle("t2", fetched)
    assert result.status == "SUCCESS"
    assert "security" in result.applied_components

    # Test tampering
    fetched.signature_hash = "invalid"
    with pytest.raises(Exception, match="tampering"):
        installer.install_bundle("t2", fetched)
