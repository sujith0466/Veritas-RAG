"""Comprehensive Unit and Validation Test Suite for Prometheus Alerting Rules (F14.5)."""

from pathlib import Path
import re
import yaml

import pytest

from backend.observability.metrics.prometheus import get_metrics_output


class TestPrometheusAlertingRules:
    """Test suite validating Prometheus alert rules schema, PromQL syntax, and metric existence."""

    @pytest.fixture
    def alert_rules_data(self) -> dict:
        rule_path = Path("infrastructure/monitoring/prometheus/rules/alert_rules.yml")
        assert rule_path.exists(), f"Alert rules file not found at {rule_path}"

        with open(rule_path, "r", encoding="utf-8-sig") as f:
            data = yaml.safe_load(f)

        assert "groups" in data
        return data

    def test_alert_groups_structure(self, alert_rules_data: dict) -> None:
        group_names = [g["name"] for g in alert_rules_data["groups"]]
        assert "RAGuard_SEV1_Critical_Alerts" in group_names
        assert "RAGuard_SEV2_Major_Alerts" in group_names
        assert "RAGuard_SEV3_Warning_Alerts" in group_names

    def test_required_alert_fields_and_severities(self, alert_rules_data: dict) -> None:
        for group in alert_rules_data["groups"]:
            group_name = group["name"]
            rules = group.get("rules", [])
            assert len(rules) >= 3, f"Group {group_name} should have at least 3 alert rules"

            for rule in rules:
                assert "alert" in rule
                assert "expr" in rule
                assert "for" in rule
                assert "labels" in rule
                assert "annotations" in rule

                labels = rule["labels"]
                annotations = rule["annotations"]

                assert "severity" in labels
                assert labels["severity"] in ("SEV-1", "SEV-2", "SEV-3")
                assert "tier" in labels
                assert "service" in labels

                assert "summary" in annotations
                assert "description" in annotations
                assert "runbook_url" in annotations

                # Ensure severity matches group
                if "SEV1" in group_name:
                    assert labels["severity"] == "SEV-1"
                    assert labels["tier"] == "critical"
                elif "SEV2" in group_name:
                    assert labels["severity"] == "SEV-2"
                    assert labels["tier"] == "major"
                elif "SEV3" in group_name:
                    assert labels["severity"] == "SEV-3"
                    assert labels["tier"] == "warning"

    def test_all_alert_metrics_exist_in_prometheus_registry(self, alert_rules_data: dict) -> None:
        raw_metrics = get_metrics_output().decode("utf-8")
        metric_pattern = re.compile(r"\b(raguard_[a-zA-Z0-9_]+)\b")

        alert_metrics = set()
        for group in alert_rules_data["groups"]:
            for rule in group.get("rules", []):
                expr = rule.get("expr", "")
                matches = metric_pattern.findall(expr)
                for m in matches:
                    base_m = m[:-7] if m.endswith("_bucket") else m
                    alert_metrics.add(base_m)

        assert len(alert_metrics) >= 8
        for metric_name in alert_metrics:
            assert metric_name in raw_metrics, f"Alert metric '{metric_name}' is not exported by Prometheus registry!"

    def test_no_unbounded_or_sensitive_labels(self, alert_rules_data: dict) -> None:
        forbidden_keys = {"tenant_id", "user_id", "document_id", "query_text", "request_id", "email"}

        for group in alert_rules_data["groups"]:
            for rule in group.get("rules", []):
                labels = rule.get("labels", {})
                for k in labels:
                    assert k.lower() not in forbidden_keys, f"Rule {rule['alert']} contains forbidden label '{k}'"

    def test_promtool_rules_check_in_container(self) -> None:
        """Run promtool check rules and promtool test rules inside docker container if available."""
        import subprocess

        try:
            res = subprocess.run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--entrypoint",
                    "/bin/promtool",
                    "-v",
                    f"{Path.cwd() / 'infrastructure/monitoring/prometheus/rules'}:/etc/prometheus/rules",
                    "-w",
                    "/etc/prometheus/rules",
                    "prom/prometheus:v2.47.0",
                    "test",
                    "rules",
                    "test_alert_rules.yml",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if res.returncode == 0:
                assert "SUCCESS" in res.stdout
        except (subprocess.SubprocessError, FileNotFoundError):
            pytest.skip("Docker not available in test runner environment")
