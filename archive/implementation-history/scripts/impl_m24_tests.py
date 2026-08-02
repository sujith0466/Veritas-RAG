import os
import sys
import subprocess

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

def main():
    print("Starting Milestone 24.4 Implementation (Tests)...")
    os.makedirs("tests/unit/backend/modules/marketplace", exist_ok=True)
    
    # 1. test_bundle.py
    with open("tests/unit/backend/modules/marketplace/test_bundle.py", "w") as f:
        f.write("""import pytest
from backend.modules.marketplace.services.bundle import BundleService, BundleInstaller
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
""")

    print("Created test files.")
    
    print("Running tests...")
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/unit/backend/modules/marketplace"], capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        sys.exit(1)

    print("Milestone 24.4 completed.")

if __name__ == "__main__":
    main()
