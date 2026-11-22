"""Atomic Write Module for HATE Local Store.

Implements atomic file write pattern: temp write → fsync/rename → manifest complete.
Handles partial write quarantine and corruption detection.

No-Go conditions:
- Partial write appears as valid run
- Atomic write without fsync
- Rename without manifest completion check
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import warnings
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .manifest_validation import manifest_errors


@dataclass
class AtomicWriteError(Exception):
    """Error during atomic write operation."""
    message: str
    path: Path
    phase: str  # "write", "fsync", "rename", "manifest"
    diagnostics: list[dict[str, Any]] = field(default_factory=list)

    def __str__(self) -> str:
        return f"AtomicWriteError({self.phase}): {self.message} at {self.path}"


def atomic_write_json(
    target_path: Path,
    content: dict[str, Any],
    store_root: Path,
) -> Path:
    """JSONを検証してから、UTF-8・LFの固定形式で原子的に保存する。"""
    if not isinstance(content, dict):
        raise AtomicWriteError(
            message="Content must be a JSON object (dict)",
            path=target_path,
            phase="write",
            diagnostics=[{"issue": "invalid_content_type", "type": str(type(content))}],
        )

    try:
        payload = (json.dumps(content, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise AtomicWriteError(str(exc), target_path, "write") from exc
    return atomic_write_bytes(target_path, payload, store_root)


def atomic_write_bytes(target_path: Path, content: bytes, store_root: Path) -> Path:
    """全バイトの書き込みとfsync後に、既存ファイルを直接置換する。

    置換前の失敗では旧ファイルを保持する。置換後のdirectory fsync失敗は
    diagnosticsのpublished=trueで区別し、書き込み自体の巻き戻しは行わない。
    """
    _validate_path_within_store(target_path, store_root)
    temp_fd = None
    temp_path = None
    phase = "write"
    published = False
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temp_fd, temp_path = tempfile.mkstemp(
            dir=target_path.parent,
            prefix=".tmp-",
            suffix=target_path.suffix,
        )

        remaining = memoryview(content)
        while remaining:
            written = os.write(temp_fd, remaining)
            if written <= 0:
                raise OSError("write made no progress")
            remaining = remaining[written:]
        phase = "fsync"
        os.fsync(temp_fd)
        os.close(temp_fd)
        temp_fd = None

        phase = "rename"
        os.replace(temp_path, target_path)
        published = True
        temp_path = None
        phase = "fsync"
        _sync_parent_directory(target_path.parent)
        return target_path
    except Exception as exc:
        raise AtomicWriteError(
            message=str(exc), path=target_path, phase=phase,
            diagnostics=[{"exception": type(exc).__name__, "message": str(exc), "published": published}],
        ) from exc
    finally:
        if temp_fd is not None:
            try:
                os.close(temp_fd)
            except OSError:
                pass
        if temp_path is not None:
            try:
                Path(temp_path).unlink(missing_ok=True)
            except OSError as exc:
                warnings.warn(f"temporary store file retained: {temp_path}: {exc}", RuntimeWarning, stacklevel=2)


def _sync_parent_directory(parent: Path) -> None:
    if os.name == "nt":
        return
    parent_fd = os.open(parent, os.O_RDONLY)
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)


def complete_manifest_write(
    manifest_path: Path,
    manifest_content: dict[str, Any],
    store_root: Path,
    bundle_files: list[Path],
) -> dict[str, Any]:
    """Write store manifest atomically, marking bundle as complete.

    The manifest is written atomically with completed=true only after
    all bundle files are successfully written and verified.

    Args:
        manifest_path: Path to store-manifest.json
        manifest_content: Manifest content (updated only after successful publication and sync)
        store_root: Root of store for path traversal check
        bundle_files: Caller-required files, checked in addition to the canonical bundle and artifact inventory

    Returns:
        Written manifest with diagnostics

    Raises:
        AtomicWriteError: If verification or write fails
    """
    from .completion import complete_manifest_write as complete

    return complete(manifest_path, manifest_content, store_root, bundle_files)


def quarantine_partial_write(
    store_root: Path,
    run_id: str,
    partial_files: list[Path],
    error: AtomicWriteError,
) -> Path:
    """Quarantine a partial/incomplete write for later diagnosis.

    Creates a quarantine directory with:
    - Partial files moved to quarantine
    - Error diagnostics preserved
    - Quarantine manifest created

    Args:
        store_root: Root of store
        run_id: Run ID for the partial write
        partial_files: Files that were partially written
        error: The error that caused the partial write

    Returns:
        Path to quarantine manifest

    Raises:
        AtomicWriteError: If quarantine write fails
    """
    quarantine_dir = store_root / "quarantine" / run_id
    quarantine_dir.mkdir(parents=True, exist_ok=True)

    # Move partial files to quarantine
    moved_files = []
    for partial_file in partial_files:
        if partial_file.exists():
            dest = quarantine_dir / partial_file.name
            shutil.move(str(partial_file), str(dest))
            moved_files.append(str(dest))

    # Create quarantine manifest
    quarantine_manifest = {
        "schema_version": "HATE/v1",
        "record_type": "quarantine_manifest",
        "run_id": run_id,
        "quarantine_reason": error.phase,
        "quarantined_at": datetime.now(UTC).isoformat(),
        "original_error": {
            "message": error.message,
            "path": str(error.path),
            "phase": error.phase,
            "diagnostics": error.diagnostics,
        },
        "quarantined_files": moved_files,
        "diagnostic_required": True,
        "recovery_possible": error.phase in ["write", "fsync"],
    }

    quarantine_manifest_path = quarantine_dir / "quarantine-manifest.json"
    atomic_write_json(quarantine_manifest_path, quarantine_manifest, store_root)

    return quarantine_manifest_path


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA256 hash of a file.

    Args:
        file_path: Path to file

    Returns:
        Hash string in format "sha256:<hex>"
    """
    sha256 = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return f"sha256:{sha256.hexdigest()}"


def compute_json_hash(content: dict[str, Any]) -> str:
    """Compute stable SHA256 hash of JSON content.

    Uses sorted keys and minimal separators for deterministic hashing.

    Args:
        content: JSON object to hash

    Returns:
        Hash string in format "sha256:<hex>"
    """
    payload = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    sha256 = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"sha256:{sha256}"


def compute_json_hash_for_write(content: dict[str, Any]) -> str:
    """Compute SHA256 hash of JSON content in write format (indent=2).

    This matches the format used by atomic_write_json for consistent hashing.

    Args:
        content: JSON object to hash

    Returns:
        Hash string in format "sha256:<hex>"
    """
    payload = json.dumps(content, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    sha256 = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"sha256:{sha256}"


def _validate_path_within_store(path: Path, store_root: Path) -> None:
    """Validate that path resolves within store root.

    Rejects path traversal attempts (e.g., "../../../etc/passwd").

    Args:
        path: Path to validate
        store_root: Store root directory

    Raises:
        AtomicWriteError: If path escapes store root
    """
    # Resolve both paths to absolute
    resolved_path = path.resolve()
    resolved_root = store_root.resolve()

    # Check if resolved path is within store root
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise AtomicWriteError(
            message="Path traversal attempt rejected",
            path=path,
            phase="write",
            diagnostics=[
                {
                    "issue": "path_traversal",
                    "resolved_path": str(resolved_path),
                    "store_root": str(resolved_root),
                }
            ],
        ) from exc


def is_complete_manifest(manifest_path: Path) -> bool:
    """Check if a manifest indicates a complete bundle.

    Args:
        manifest_path: Path to store-manifest.json

    Returns:
        True if the manifest is schema-valid and completed=true (file integrity is separate)
    """
    if not manifest_path.exists():
        return False

    try:
        from .json_io import strict_json_loads

        manifest = strict_json_loads(manifest_path.read_text(encoding="utf-8"))
        return not manifest_errors(manifest) and manifest["completed"] is True
    except (ValueError, OSError):
        return False
