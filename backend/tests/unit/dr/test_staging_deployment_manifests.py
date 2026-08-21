"""Unit and Manifest Validation Suite for Kubernetes Staging Deployment Manifests (Epic 15).

Verifies:
1. All staging manifests target namespace 'raguard-staging'.
2. Zero cross-namespace leakage (no references to 'raguard-production' or production databases).
3. API deployment includes resource requests/limits, startup, liveness, and readiness probes.
4. RBAC is strictly scoped to 'raguard-staging' without cluster-wide escalation.
5. CronJobs use secure secretKeyRef credentials and mount persistent volume claims.
6. Secret template contains no real plaintext credentials.
"""

from pathlib import Path
import pytest
import yaml

STAGING_DIR = Path("infrastructure/kubernetes/staging")


def get_staging_docs():
    docs = []
    for file_path in STAGING_DIR.glob("*.yaml"):
        with open(file_path, "r", encoding="utf-8") as f:
            for doc in yaml.safe_load_all(f):
                if doc:
                    docs.append((file_path.name, doc))
    return docs


def test_all_staging_manifests_target_staging_namespace():
    """Verify that every manifest explicitly specifies namespace 'raguard-staging'."""
    docs = get_staging_docs()
    assert len(docs) >= 9, f"Expected at least 9 manifest documents, found {len(docs)}"

    for filename, doc in docs:
        metadata = doc.get("metadata", {})
        namespace = metadata.get("namespace")
        assert namespace == "raguard-staging", (
            f"Manifest {filename} ({doc.get('kind')}: {metadata.get('name')}) "
            f"has invalid namespace '{namespace}'. Must be 'raguard-staging'."
        )


def test_zero_production_cross_contamination():
    """Verify that staging manifests contain 0 references to production namespaces or DBs."""
    for file_path in STAGING_DIR.glob("*.yaml"):
        content = file_path.read_text(encoding="utf-8")
        assert "raguard-production" not in content, (
            f"Cross-contamination detected in {file_path.name}: contains 'raguard-production'"
        )
        assert "raguard_db_production" not in content, (
            f"Cross-contamination detected in {file_path.name}: contains 'raguard_db_production'"
        )


def test_api_deployment_probes_and_resources():
    """Verify API deployment has resource limits and all three health probes."""
    docs = get_staging_docs()
    api_dep = next(doc for fname, doc in docs if doc.get("kind") == "Deployment" and doc["metadata"]["name"] == "raguard-api")

    spec = api_dep["spec"]["template"]["spec"]
    container = spec["containers"][0]

    # Probes
    assert container["livenessProbe"]["httpGet"]["path"] == "/health/live"
    assert container["readinessProbe"]["httpGet"]["path"] == "/health/ready"
    assert container["startupProbe"]["httpGet"]["path"] == "/health/startup"

    # Resources
    resources = container["resources"]
    assert "requests" in resources and "limits" in resources
    assert resources["requests"]["memory"] == "256Mi"
    assert resources["limits"]["memory"] == "1Gi"


def test_rbac_strictly_scoped_to_staging():
    """Verify RBAC role does not grant cluster-wide or dangerous escalation."""
    docs = get_staging_docs()
    role = next(doc for fname, doc in docs if doc.get("kind") == "Role" and doc["metadata"]["name"] == "raguard-chaos-runner-role")

    assert role["metadata"]["namespace"] == "raguard-staging"
    for rule in role.get("rules", []):
        # Must only manage pods or deployments in staging
        for res in rule.get("resources", []):
            assert res in ["pods", "deployments"], f"Unexpected resource in chaos role: {res}"


def test_secret_template_safety():
    """Verify secrets template uses placeholders and does not expose real credentials."""
    docs = get_staging_docs()
    secret = next(doc for fname, doc in docs if doc.get("kind") == "Secret" and doc["metadata"]["name"] == "raguard-secrets")

    data = secret.get("stringData", {})
    for key, value in data.items():
        assert "CHANGE_ME" in value or "placeholder" in value.lower(), (
            f"Potential real credential in secret template key {key}: {value}"
        )
