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
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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
    """Write JSON atomically with temp file, fsync, and rename.

    Pattern:
    1. Write to temp file in same directory
    2. Fsync temp file and parent directory
    3. Rename temp to target (atomic on same filesystem)
    4. Fsync parent directory again

    Args:
        target_path: Final destination path
        content: JSON content to write
        store_root: Root of store for path traversal check

    Returns:
        Path to written file

    Raises:
        AtomicWriteError: If any phase fails
    """
    # Path traversal rejection
    _validate_path_within_store(target_path, store_root)

    # Ensure parent directory exists
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # Validate content is a dict
    if not isinstance(content, dict):
        raise AtomicWriteError(
            message="Content must be a JSON object (dict)",
            path=target_path,
            phase="write",
            diagnostics=[{"issue": "invalid_content_type", "type": str(type(content))}],
        )

    # Create temp file in same directory for atomic rename
    temp_fd = None
    temp_path = None
    try:
        # Phase 1: Write to temp file
        temp_fd, temp_path = tempfile.mkstemp(
            dir=target_path.parent,
            prefix=".tmp-",
            suffix=target_path.suffix,
        )

        # Write JSON content
        payload = json.dumps(content, ensure_ascii=False, indent=2) + "\n"
        os.write(temp_fd, payload.encode("utf-8"))

        # Phase 2: Fsync temp file
        os.fsync(temp_fd)
        os.close(temp_fd)
        temp_fd = None

        # Phase 3: Rename (atomic on same filesystem)
        if target_path.exists():
            # On Windows, need to remove target first
            if os.name == "nt":
                # Use replace with backup for Windows atomicity
                backup_path = target_path.with_suffix(target_path.suffix + ".bak")
                shutil.move(str(target_path), str(backup_path))
                shutil.move(str(temp_path), str(target_path))
                backup_path.unlink(missing_ok=True)
            else:
                os.replace(temp_path, target_path)
        else:
            shutil.move(str(temp_path), str(target_path))

        temp_path = None

        # Phase 4: Fsync parent directory (Unix/Linux only)
        # On Windows, directory fsync is not required/supported via os.open
        if os.name != "nt":
            parent_fd = os.open(target_path.parent, os.O_RDONLY)
            os.fsync(parent_fd)
            os.close(parent_fd)

        return target_path

    except Exception as e:
        # Cleanup temp file on failure
        if temp_fd is not None:
            try:
                os.close(temp_fd)
            except OSError:
                pass
        if temp_path is not None and Path(temp_path).exists():
            Path(temp_path).unlink(missing_ok=True)

        raise AtomicWriteError(
            message=str(e),
            path=target_path,
            phase="write",
            diagnostics=[{"exception": type(e).__name__, "message": str(e)}],
        ) from e


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
        manifest_content: Manifest content (will set completed=true)
        store_root: Root of store for path traversal check
        bundle_files: List of bundle files that must exist before manifest

    Returns:
        Written manifest with diagnostics

    Raises:
        AtomicWriteError: If verification or write fails
    """
    # Verify all bundle files exist
    missing_files = [f for f in bundle_files if not f.exists()]
    if missing_files:
        raise AtomicWriteError(
            message="Bundle files missing before manifest completion",
            path=manifest_path,
            phase="manifest",
            diagnostics=[
                {"issue": "missing_bundle_file", "path": str(f)}
                for f in missing_files
            ],
        )

    # Verify content hashes match
    hash_mismatches = []
    for file_path in bundle_files:
        if file_path.suffix == ".json" and file_path.name != "store-manifest.json":
            try:
                actual_hash = compute_file_hash(file_path)
                # Check if manifest_content has expected hash
                expected_hash = manifest_content.get("content_hashes", {}).get(
                    file_path.stem, None
                )
                if expected_hash and actual_hash != expected_hash:
                    hash_mismatches.append({
                        "file": str(file_path),
                        "expected": expected_hash,
                        "actual": actual_hash,
                    })
            except Exception as e:
                hash_mismatches.append({
                    "file": str(file_path),
                    "error": str(e),
                })

    if hash_mismatches:
        raise AtomicWriteError(
            message="Content hash mismatch detected",
            path=manifest_path,
            phase="manifest",
            diagnostics=hash_mismatches,
        )

    # Set completed=true
    manifest_content["completed"] = True
    manifest_content["import_status"] = {
        "phase": "completed",
        "diagnostics": [],
    }

    # Write manifest atomically
    atomic_write_json(manifest_path, manifest_content, store_root)

    return manifest_content


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
        "quarantined_at": datetime.now(timezone.utc).isoformat(),
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
    payload = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
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
    payload = json.dumps(content, ensure_ascii=False, indent=2) + "\n"
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
    except ValueError:
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
        )


def is_complete_manifest(manifest_path: Path) -> bool:
    """Check if a manifest indicates a complete bundle.

    Args:
        manifest_path: Path to store-manifest.json

    Returns:
        True if manifest exists and completed=true, False otherwise
    """
    if not manifest_path.exists():
        return False

    try:
        with manifest_path.open("r", encoding="utf-8") as f:
            manifest = json.load(f)
        return manifest.get("completed", False) is True
    except (json.JSONDecodeError, OSError):
        return False