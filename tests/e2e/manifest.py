"""Canonical build-context manifest and source digest generator for Veritas-RAG.

Computes a deterministic, cryptographic SHA-256 digest over the exact effective
Docker build context (accounting for .dockerignore rules) without altering any source
files or requiring working tree changes to be committed.
"""

from __future__ import annotations

import fnmatch
import hashlib
import os
from pathlib import Path
import sys
import tarfile
from typing import NamedTuple


# Root build inputs explicitly specified in Dockerfile or build context
REQUIRED_ROOT_FILES = (
    "Dockerfile",
    ".dockerignore",
    "requirements.txt",
    "alembic.ini",
    "pyproject.toml",
)

REQUIRED_DIRECTORIES = (
    "backend",
)


class ManifestEntry(NamedTuple):
    normalized_path: str
    sha256_hex: str
    size_bytes: int


class DockerignoreMatcher:
    """Parses .dockerignore rules and evaluates paths against them."""

    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self.rules: list[tuple[bool, str]] = []  # (is_negation, pattern)
        dockerignore_path = root_dir / ".dockerignore"
        if not dockerignore_path.exists():
            raise FileNotFoundError(f"Missing required .dockerignore at {dockerignore_path}")

        with open(dockerignore_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                is_negation = line.startswith("!")
                pattern = line[1:].strip() if is_negation else line
                # Normalize slashes
                pattern = pattern.replace("\\", "/")
                self.rules.append((is_negation, pattern))

    def is_ignored(self, rel_path: str, is_dir: bool = False) -> bool:
        """Evaluate whether a relative POSIX path is ignored by .dockerignore."""
        ignored = False
        norm_path = rel_path.rstrip("/")
        parts = norm_path.split("/")

        for is_negation, pattern in self.rules:
            pat = pattern.rstrip("/")
            matched = False

            # Case 1: Wildcard matching directly on relative path
            if fnmatch.fnmatch(norm_path, pat):
                matched = True
            # Case 2: Pattern matches any path component (e.g. __pycache__, *.pyc)
            elif not pat.startswith("/") and not "/" in pat:
                if any(fnmatch.fnmatch(part, pat) for part in parts):
                    matched = True
            # Case 3: Leading or mid-path glob (e.g. **/node_modules, coverage/)
            elif pat.startswith("**/"):
                sub_pat = pat[3:]
                if fnmatch.fnmatch(norm_path, sub_pat) or any(fnmatch.fnmatch("/".join(parts[i:]), sub_pat) for i in range(len(parts))):
                    matched = True
            elif norm_path.startswith(pat + "/") or norm_path == pat:
                matched = True

            if matched:
                ignored = not is_negation

        return ignored


def compute_file_sha256(file_path: Path) -> str:
    """Read file in raw binary mode and compute its SHA-256 hex digest."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def scan_effective_build_inputs(root_dir: Path) -> list[tuple[str, Path]]:
    """Scan all effective build inputs, validating constraints and respecting .dockerignore.

    Returns:
        List of (normalized_posix_path, absolute_file_path) tuples.
    """
    matcher = DockerignoreMatcher(root_dir)
    eligible: list[tuple[str, Path]] = []
    seen_case_folded: dict[str, str] = {}

    # 1. Process required root files
    for root_file in REQUIRED_ROOT_FILES:
        file_path = root_dir / root_file
        if not file_path.exists() or not file_path.is_file():
            raise FileNotFoundError(f"Required root build input missing or not a file: {root_file}")
        if file_path.is_symlink():
            raise RuntimeError(f"FATAL: Symlinks not permitted in build context: {root_file}")

        posix_rel = root_file.replace("\\", "/")
        # .dockerignore may specify !.dockerignore or Dockerfile*; check other root inputs
        if posix_rel not in (".dockerignore", "Dockerfile") and matcher.is_ignored(posix_rel, is_dir=False):
            # If a required root file is ignored, that is a configuration error
            raise RuntimeError(f"Required root build input is unexpectedly ignored by .dockerignore: {posix_rel}")

        folded = posix_rel.lower()
        if folded in seen_case_folded:
            raise RuntimeError(f"FATAL: Case collision detected between '{posix_rel}' and '{seen_case_folded[folded]}'")
        seen_case_folded[folded] = posix_rel
        eligible.append((posix_rel, file_path))

    # 2. Process directories (e.g. backend/)
    for dir_name in REQUIRED_DIRECTORIES:
        dir_path = root_dir / dir_name
        if not dir_path.exists() or not dir_path.is_dir():
            raise FileNotFoundError(f"Required build directory missing: {dir_name}")

        for dirpath, dirnames, filenames in os.walk(dir_path, followlinks=False):
            current_dir = Path(dirpath)
            rel_dir = current_dir.relative_to(root_dir).as_posix()

            # Check if directory itself is ignored
            if matcher.is_ignored(rel_dir, is_dir=True):
                dirnames.clear()  # Do not recurse into ignored directories
                continue

            # Detect directory symlinks
            for d in list(dirnames):
                sub_d = current_dir / d
                if sub_d.is_symlink():
                    raise RuntimeError(f"FATAL: Symlinks not permitted in build context: {sub_d}")

            for fname in filenames:
                fpath = current_dir / fname
                if fpath.is_symlink():
                    raise RuntimeError(f"FATAL: Symlinks not permitted in build context: {fpath}")

                posix_rel = fpath.relative_to(root_dir).as_posix()

                # Reject path traversal
                if posix_rel.startswith("../") or "/../" in posix_rel:
                    raise RuntimeError(f"FATAL: Path traversal detected in: {posix_rel}")

                # Check if file is ignored by .dockerignore
                if matcher.is_ignored(posix_rel, is_dir=False):
                    continue

                folded = posix_rel.lower()
                if folded in seen_case_folded and seen_case_folded[folded] != posix_rel:
                    raise RuntimeError(f"FATAL: Case collision detected between '{posix_rel}' and '{seen_case_folded[folded]}'")
                seen_case_folded[folded] = posix_rel

                eligible.append((posix_rel, fpath))

    # Deterministic ordinal byte sort by normalized UTF-8 path
    eligible.sort(key=lambda item: item[0].encode("utf-8"))
    return eligible


def generate_manifest(root_dir: Path) -> tuple[str, list[ManifestEntry], str]:
    """Generate the canonical manifest and SHA-256 source digest.

    Returns:
        tuple of (source_digest_hex, list_of_entries, formatted_manifest_string)
    """
    eligible = scan_effective_build_inputs(root_dir)
    entries: list[ManifestEntry] = []
    manifest_lines: list[str] = []

    for posix_rel, fpath in eligible:
        file_sha = compute_file_sha256(fpath)
        size = fpath.stat().st_size
        entries.append(ManifestEntry(posix_rel, file_sha, size))
        # Canonical framing: <path_len_utf8>:<path>:<sha256>\n
        path_len = len(posix_rel.encode("utf-8"))
        manifest_lines.append(f"{path_len}:{posix_rel}:{file_sha}\n")

    manifest_content = "".join(manifest_lines)
    source_digest = hashlib.sha256(manifest_content.encode("utf-8")).hexdigest()
    return source_digest, entries, manifest_content


def create_context_snapshot(root_dir: Path, output_tar: Path) -> tuple[str, str, int]:
    """Capture an immutable build-context snapshot tarball and compute its digests.

    Returns:
        tuple of (source_digest, tar_sha256, file_count)
    """
    source_digest, entries, manifest_content = generate_manifest(root_dir)
    output_tar.parent.mkdir(parents=True, exist_ok=True)

    # Build canonical uncompressed tar with normalized metadata
    with tarfile.open(output_tar, "w") as tar:
        # 1. Add canonical .source_manifest at tar root
        manifest_bytes = manifest_content.encode("utf-8")
        manifest_info = tarfile.TarInfo(name=".source_manifest")
        manifest_info.size = len(manifest_bytes)
        manifest_info.mtime = 0
        manifest_info.mode = 0o644
        manifest_info.uid = 0
        manifest_info.gid = 0
        manifest_info.uname = "root"
        manifest_info.gname = "root"
        import io
        tar.addfile(manifest_info, io.BytesIO(manifest_bytes))

        # 2. Add each eligible file in sorted order
        for entry in entries:
            file_path = root_dir / entry.normalized_path
            with open(file_path, "rb") as f:
                tar_info = tarfile.TarInfo(name=entry.normalized_path)
                tar_info.size = entry.size_bytes
                tar_info.mtime = 0
                tar_info.mode = 0o644
                tar_info.uid = 0
                tar_info.gid = 0
                tar_info.uname = "root"
                tar_info.gname = "root"
                tar.addfile(tar_info, f)

    tar_sha = compute_file_sha256(output_tar)
    return source_digest, tar_sha, len(entries)


def verify_manifest(root_dir: Path, expected_digest: str | None = None) -> tuple[bool, str]:
    """Verify that current working tree matches an expected digest or is internally consistent.

    Returns:
        tuple of (is_valid: bool, detail_message: str)
    """
    source_digest, entries, _ = generate_manifest(root_dir)
    if expected_digest is not None and source_digest != expected_digest.strip():
        return False, f"Source digest mismatch: computed {source_digest}, expected {expected_digest.strip()}"
    return True, f"Verified: {len(entries)} effective build inputs match digest {source_digest}"


def main() -> int:
    """CLI entry point for manifest operations."""
    root_dir = Path(__file__).resolve().parent.parent.parent
    args = sys.argv[1:]
    command = args[0] if args else "digest"

    try:
        if command == "digest":
            source_digest, entries, _ = generate_manifest(root_dir)
            sys.stdout.write(source_digest + "\n")
            return 0
        elif command == "manifest":
            _, _, manifest_content = generate_manifest(root_dir)
            sys.stdout.write(manifest_content)
            return 0
        elif command == "count":
            _, entries, _ = generate_manifest(root_dir)
            sys.stdout.write(f"{len(entries)}\n")
            return 0
        elif command == "verify":
            expected = args[1] if len(args) > 1 else None
            ok, msg = verify_manifest(root_dir, expected)
            if not ok:
                sys.stderr.write(f"FATAL: {msg}\n")
                return 1
            sys.stdout.write(f"{msg}\n")
            return 0
        elif command == "create-snapshot":
            if len(args) < 2:
                sys.stderr.write("Usage: manifest.py create-snapshot <output_tar_path>\n")
                return 1
            out_tar = Path(args[1]).resolve()
            source_digest, tar_sha, count = create_context_snapshot(root_dir, out_tar)
            sys.stdout.write(f"SOURCE_DIGEST={source_digest}\n")
            sys.stdout.write(f"SNAPSHOT_TAR_SHA256={tar_sha}\n")
            sys.stdout.write(f"FILE_COUNT={count}\n")
            return 0
        else:
            sys.stderr.write(f"Unknown command: '{command}'. Use 'digest', 'manifest', 'count', 'verify', or 'create-snapshot'.\n")
            return 1
    except Exception as exc:
        sys.stderr.write(f"FATAL: Manifest generation failed: {exc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
