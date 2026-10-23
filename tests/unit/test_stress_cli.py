"""Unit tests for the stress test CLI and safety configuration validation.

Tests verify argument parsing, required arguments, URL validation,
container discovery integration, and fail-closed safety guards.
"""

from unittest.mock import patch
import pytest

from tests.performance.stress.stress_test import (
    MemoryDiscoveryFailure,
    StressTestConfigError,
    main,
    parse_args,
    validate_stress_test_config,
)


class TestStressCliParsing:
    """Verifies CLI argument parsing and flags."""

    def test_parse_args_valid_minimal(self) -> None:
        """--target is required and defaults are applied."""
        args = parse_args(["--target", "http://localhost:8001"])
        assert args.target == "http://localhost:8001"
        assert args.container == "veritas-rag-api-1"
        assert args.validate_only is False
        assert args.dry_run is False
        assert args.execute is False

    def test_parse_args_all_options(self) -> None:
        """All options are parsed cleanly."""
        args = parse_args(
            [
                "--target",
                "https://perf.internal:8443",
                "--container",
                "bench-api-container",
                "--validate-only",
                "--dry-run",
                "--execute",
            ]
        )
        assert args.target == "https://perf.internal:8443"
        assert args.container == "bench-api-container"
        assert args.validate_only is True
        assert args.dry_run is True
        assert args.execute is True

    def test_parse_args_missing_target_exits(self) -> None:
        """Missing required --target argument fails parsing."""
        with pytest.raises(SystemExit):
            parse_args(["--container", "test-box"])

    def test_parse_args_unknown_argument_exits(self) -> None:
        """Unknown flags trigger strict parser failure."""
        with pytest.raises(SystemExit):
            parse_args(["--target", "http://localhost:8001", "--unsupported-option"])


class TestStressConfigValidation:
    """Verifies target URL validation and container memory safety discovery."""

    def test_validate_config_success(self) -> None:
        """Valid target and discovered container limits return config dictionary."""
        args = parse_args(["--target", "http://localhost:8001", "--container", "test-api"])
        with patch(
            "tests.performance.stress.stress_test.discover_container_memory_limit",
            return_value=2 * 1024 * 1024 * 1024,  # 2 GiB
        ):
            config = validate_stress_test_config(args)

        assert config["target"] == "http://localhost:8001"
        assert config["container"] == "test-api"
        assert config["memory_limit_bytes"] == 2 * 1024 * 1024 * 1024
        assert config["abort_threshold_bytes"] == int(2 * 1024 * 1024 * 1024 * 0.90)
        assert config["execute_authorized"] is False

    @pytest.mark.parametrize(
        "invalid_target",
        [
            "localhost:8001",
            "ftp://localhost:8001",
            "://invalid",
            "http://",
            "not-a-url",
        ],
    )
    def test_validate_config_malformed_target_raises(self, invalid_target: str) -> None:
        """Malformed target URLs fail closed before any container or network action."""
        args = parse_args(["--target", invalid_target])
        with pytest.raises(StressTestConfigError, match="CRITICAL SAFETY ABORT: Malformed target URL"):
            validate_stress_test_config(args)

    def test_validate_config_memory_discovery_failure_raises(self) -> None:
        """If container limit discovery fails, config validation fails closed."""
        args = parse_args(["--target", "http://localhost:8001", "--container", "non-existent"])
        with patch(
            "tests.performance.stress.stress_test.discover_container_memory_limit",
            side_effect=MemoryDiscoveryFailure("Could not query docker inspect for non-existent"),
        ):
            with pytest.raises(StressTestConfigError, match="Could not query docker inspect"):
                validate_stress_test_config(args)


class TestStressMainEntryPoint:
    """Verifies the main() CLI execution guard and exit codes."""

    def test_main_validate_only_exits_zero(self) -> None:
        """--validate-only performs discovery check and exits with 0 without running traffic."""
        with patch(
            "tests.performance.stress.stress_test.discover_container_memory_limit",
            return_value=1024 * 1024 * 1024,
        ):
            exit_code = main(["--target", "http://localhost:8001", "--validate-only"])
            assert exit_code == 0

    def test_main_invalid_target_exits_nonzero(self) -> None:
        """Invalid target URL prints error and exits with 1."""
        exit_code = main(["--target", "invalid-target", "--validate-only"])
        assert exit_code == 1

    def test_main_execute_flag_halts_safely(self) -> None:
        """Passing --execute triggers safety halt pending explicit operator authorization."""
        with patch(
            "tests.performance.stress.stress_test.discover_container_memory_limit",
            return_value=1024 * 1024 * 1024,
        ):
            with pytest.raises(RuntimeError, match="Live saturation/stress execution is halted"):
                main(["--target", "http://localhost:8001", "--execute"])
