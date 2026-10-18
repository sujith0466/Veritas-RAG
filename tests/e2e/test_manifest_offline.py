"""Offline static unit tests for the canonical build-context manifest generator.

Tests determinism, .dockerignore rule parsing, exclusion compliance, and error guards
without requiring any Docker daemon, database, broker, or live services.
"""

from __future__ import annotations

import io
from pathlib import Path
import tarfile
import tempfile
import pytest

from tests.e2e.manifest import (
    DockerignoreMatcher,
    generate_manifest,
    scan_effective_build_inputs,
    create_context_snapshot,
)


@pytest.fixture(scope="module")
def repo_root() -> Path:
    """Return repository root path."""
    return Path(__file__).resolve().parent.parent.parent


def test_dockerignore_rules_parsed(repo_root: Path):
    """Verify that .dockerignore is parsed and critical exclusion patterns are present."""
    matcher = DockerignoreMatcher(repo_root)
    assert len(matcher.rules) > 10, "Should load rules from .dockerignore"

    # Pycache and pyc must be ignored
    assert matcher.is_ignored("backend/ai/__pycache__", is_dir=True) is True
    assert matcher.is_ignored("backend/ai/__pycache__/foo.pyc", is_dir=False) is True
    assert matcher.is_ignored("backend/test.pyc", is_dir=False) is True
    assert matcher.is_ignored("backend/test.log", is_dir=False) is True

    # .dockerignore negation must be respected
    assert matcher.is_ignored(".dockerignore", is_dir=False) is False

    # Standard python files under backend must NOT be ignored
    assert matcher.is_ignored("backend/main.py", is_dir=False) is False
    assert matcher.is_ignored("backend/document/services/document_service.py", is_dir=False) is False


def test_manifest_generation_completeness(repo_root: Path):
    """Verify that effective build inputs are discovered and canonical digest is valid."""
    source_digest, entries, manifest_content = generate_manifest(repo_root)

    # 1. Digest is 64-character lowercase hex string
    assert len(source_digest) == 64
    assert all(c in "0123456789abcdef" for c in source_digest)

    # 2. Key required root files exist in manifest
    paths = {e.normalized_path for e in entries}
    assert "Dockerfile" in paths
    assert ".dockerignore" in paths
    assert "requirements.txt" in paths
    assert "alembic.ini" in paths
    assert "pyproject.toml" in paths

    # 3. Backend files are included
    assert "backend/main.py" in paths

    # 4. Excluded files are NOT present
    for p in paths:
        assert not p.endswith(".pyc"), f"Compiled bytecode unexpectedly in manifest: {p}"
        assert "__pycache__" not in p, f"Cache directory unexpectedly in manifest: {p}"
        assert not p.endswith(".log"), f"Log file unexpectedly in manifest: {p}"
        assert not p.startswith("tests/"), f"Test file unexpectedly in application manifest: {p}"

    # 5. Manifest framing check: <len>:<path>:<sha256>\n
    lines = manifest_content.strip().split("\n")
    assert len(lines) == len(entries)
    for line in lines:
        parts = line.split(":")
        assert len(parts) == 3
        path_len = int(parts[0])
        path_str = parts[1]
        file_sha = parts[2]
        assert len(path_str.encode("utf-8")) == path_len
        assert len(file_sha) == 64


def test_manifest_determinism(repo_root: Path):
    """Verify that repeated manifest generations yield identical digests byte-for-byte."""
    digest_1, entries_1, content_1 = generate_manifest(repo_root)
    digest_2, entries_2, content_2 = generate_manifest(repo_root)

    assert digest_1 == digest_2, "Digest must be 100% deterministic"
    assert content_1 == content_2, "Manifest content must match exactly"
    assert len(entries_1) == len(entries_2)


def test_context_snapshot_tar_creation(repo_root: Path):
    """Verify that context snapshot tarball is created deterministically with .source_manifest."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tar_path = Path(tmp_dir) / "test_context.tar"
        source_digest, tar_sha, file_count = create_context_snapshot(repo_root, tar_path)

        assert tar_path.exists()
        assert len(source_digest) == 64
        assert len(tar_sha) == 64
        assert file_count > 100

        # Inspect tar contents without extracting
        with tarfile.open(tar_path, "r") as tar:
            names = tar.getnames()
            assert ".source_manifest" in names
            assert "Dockerfile" in names
            assert "requirements.txt" in names

            # Verify deterministic mtime = 0 on tar members
            for member in tar.getmembers():
                assert member.mtime == 0
                assert member.uid == 0
                assert member.gid == 0


def test_missing_required_input_rejection(tmp_path: Path):
    """Verify that scan_effective_build_inputs fails closed if a required root input is missing."""
    (tmp_path / "Dockerfile").write_text("FROM scratch\n")
    (tmp_path / ".dockerignore").write_text("# empty\n")
    # Missing requirements.txt, alembic.ini, pyproject.toml
    backend_dir = tmp_path / "backend"
    backend_dir.mkdir()
    (backend_dir / "main.py").write_text("print('hello')\n")

    with pytest.raises(FileNotFoundError, match="Required root build input missing"):
        scan_effective_build_inputs(tmp_path)


def test_symlink_rejection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify that scan_effective_build_inputs fails closed if symlinks exist in build context."""
    (tmp_path / "Dockerfile").write_text("FROM scratch\n")
    (tmp_path / ".dockerignore").write_text("# empty\n")
    (tmp_path / "requirements.txt").write_text("\n")
    (tmp_path / "alembic.ini").write_text("\n")
    (tmp_path / "pyproject.toml").write_text("\n")
    backend_dir = tmp_path / "backend"
    backend_dir.mkdir()
    (backend_dir / "main.py").write_text("print('hello')\n")

    sym_file = backend_dir / "sym.py"
    try:
        sym_file.symlink_to(backend_dir / "main.py")
    except OSError:
        # On platforms or unprivileged Windows without symlink creation rights, mock is_symlink
        sym_file.write_text("dummy")
        orig_is_symlink = Path.is_symlink
        monkeypatch.setattr(Path, "is_symlink", lambda self: True if self.name == "sym.py" else orig_is_symlink(self))

    with pytest.raises(RuntimeError, match="Symlinks not permitted in build context"):
        scan_effective_build_inputs(tmp_path)


def test_case_collision_rejection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify that case-folding collisions in build inputs fail closed."""
    (tmp_path / "Dockerfile").write_text("FROM scratch\n")
    (tmp_path / ".dockerignore").write_text("# empty\n")
    (tmp_path / "requirements.txt").write_text("\n")
    (tmp_path / "alembic.ini").write_text("\n")
    (tmp_path / "pyproject.toml").write_text("\n")
    backend_dir = tmp_path / "backend"
    backend_dir.mkdir()
    (backend_dir / "main.py").write_text("print('hello')\n")

    # Simulate os.walk yielding two files that collide case-insensitively
    import os
    orig_walk = os.walk
    def mock_walk(top, **kwargs):
        if str(top).endswith("backend"):
            yield (str(top), [], ["main.py", "MAIN.PY"])
        else:
            yield from orig_walk(top, **kwargs)

    monkeypatch.setattr(os, "walk", mock_walk)
    with pytest.raises(RuntimeError, match="Case collision detected"):
        scan_effective_build_inputs(tmp_path)


def test_path_traversal_rejection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify that path traversal sequences fail closed."""
    (tmp_path / "Dockerfile").write_text("FROM scratch\n")
    (tmp_path / ".dockerignore").write_text("# empty\n")
    (tmp_path / "requirements.txt").write_text("\n")
    (tmp_path / "alembic.ini").write_text("\n")
    (tmp_path / "pyproject.toml").write_text("\n")
    backend_dir = tmp_path / "backend"
    backend_dir.mkdir()
    (backend_dir / "main.py").write_text("print('hello')\n")

    class MockPath(type(Path())):
        def relative_to(self, *args, **kwargs):
            class FakeRel:
                def as_posix(self):
                    return "backend/../secret.txt"
            return FakeRel()

    # Intercept file path creation in backend walk
    import os
    orig_walk = os.walk
    def mock_walk(top, **kwargs):
        if str(top).endswith("backend"):
            yield (str(top), [], ["main.py"])
        else:
            yield from orig_walk(top, **kwargs)

    monkeypatch.setattr(os, "walk", mock_walk)
    orig_div = Path.__truediv__
    monkeypatch.setattr(Path, "__truediv__", lambda self, other: MockPath(orig_div(self, other)) if other == "main.py" else orig_div(self, other))

    with pytest.raises(RuntimeError, match="Path traversal detected"):
        scan_effective_build_inputs(tmp_path)


@pytest.mark.asyncio
async def test_drain_timeout_blocks_cleanup(monkeypatch: pytest.MonkeyPatch):
    """Verify that Celery drain timeout raises RuntimeError and marks cleanup BLOCKED offline."""
    from unittest.mock import AsyncMock, MagicMock
    from tests.e2e.conftest import drain_celery_queues_and_verify_quiescence

    mock_celery = MagicMock()
    mock_redis = AsyncMock()
    # Mock Redis llen returning 5 messages remaining in a queue
    mock_redis.llen = AsyncMock(return_value=5)

    monkeypatch.setattr("redis.Redis.from_url", lambda *args, **kwargs: mock_redis)
    monkeypatch.setattr("redis.asyncio.from_url", lambda *args, **kwargs: mock_redis)

    with pytest.raises(RuntimeError, match="Cleanup BLOCKED"):
        await drain_celery_queues_and_verify_quiescence(mock_celery, "redis://mock:6379/0", timeout=0.1)

    # Verify that cancel_consumer was called across all 7 queues
    assert mock_celery.control.cancel_consumer.call_count == 7


def test_manifest_verify_success_and_failure(repo_root: Path):
    """Verify verify_manifest behavior on exact match vs mismatch."""
    from tests.e2e.manifest import generate_manifest, verify_manifest

    source_digest, _, _ = generate_manifest(repo_root)

    # 1. Exact match
    ok, msg = verify_manifest(repo_root, source_digest)
    assert ok is True
    assert "Verified:" in msg

    # 2. Mismatch fails
    ok_bad, msg_bad = verify_manifest(repo_root, "bad_digest_0000000000000000000000000000000000000000000000000000000000")
    assert ok_bad is False
    assert "Source digest mismatch" in msg_bad


def test_verify_worker_provenance_offline(monkeypatch: pytest.MonkeyPatch):
    """Verify worker image ID and source digest validation in conftest."""
    import subprocess
    from tests.e2e.conftest import verify_worker_provenance

    dummy_image_id = "sha256:" + "a" * 64
    dummy_digest = "b" * 64

    # Case 1: When env vars are not set, it is a no-op
    monkeypatch.delenv("E2E_WORKER_IMAGE_ID", raising=False)
    monkeypatch.delenv("E2E_SOURCE_DIGEST", raising=False)
    verify_worker_provenance("mock_worker")  # Should not raise

    # Case 2: Matching image ID and digest
    monkeypatch.setenv("E2E_WORKER_IMAGE_ID", dummy_image_id)
    monkeypatch.setenv("E2E_SOURCE_DIGEST", dummy_digest)

    def mock_subprocess_run(cmd, *args, **kwargs):
        class Result:
            returncode = 0
            def __init__(self, stdout):
                self.stdout = stdout
        if "{{.Image}}" in cmd:
            return Result(dummy_image_id + "\n")
        elif "veritas.rag.source_digest" in cmd[-2]:
            return Result(dummy_digest + "\n")
        return Result("")

    monkeypatch.setattr(subprocess, "run", mock_subprocess_run)
    verify_worker_provenance("mock_worker")  # Should pass cleanly

    # Case 3: Mismatched image ID fails closed
    def mock_bad_image(cmd, *args, **kwargs):
        class Result:
            returncode = 0
            def __init__(self, stdout):
                self.stdout = stdout
        if "{{.Image}}" in cmd:
            return Result("sha256:" + "f" * 64 + "\n")
        return Result(dummy_digest + "\n")

    monkeypatch.setattr(subprocess, "run", mock_bad_image)
    with pytest.raises(RuntimeError, match="FATAL IMAGE ID MISMATCH"):
        verify_worker_provenance("mock_worker")

    # Case 4: Mismatched provenance digest fails closed
    def mock_bad_digest(cmd, *args, **kwargs):
        class Result:
            returncode = 0
            def __init__(self, stdout):
                self.stdout = stdout
        if "{{.Image}}" in cmd:
            return Result(dummy_image_id + "\n")
        elif "veritas.rag.source_digest" in cmd[-2]:
            return Result("mismatched_digest_value\n")
        return Result("")

    monkeypatch.setattr(subprocess, "run", mock_bad_digest)
    with pytest.raises(RuntimeError, match="FATAL IMAGE PROVENANCE MISMATCH"):
        verify_worker_provenance("mock_worker")

