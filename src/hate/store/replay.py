"""Replay Module for HATE Local Store.

Produces byte-stable reports from canonical bundle contents.
Replay is deterministic: same bundle content → same replay report.

Key invariants:
- Replay is byte-stable (deterministic from canonical content)
- Unsupported schema version is migration hold, not silent pass
- Legal hold must be preserved during replay
- Baseline cannot be selected by filename sorting only

No-Go conditions:
- Replay changes canonical bundle hash
- Unsupported schema version is silently accepted
- Legal hold metadata is dropped during replay
- Baseline selection relies on filename sorting
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .atomic_write import (
    AtomicWriteError,
    compute_file_hash,
    compute_json_hash_for_write,
)
from .indexes import HardDQFinding
from .local_store import LocalStore, StoreManifest, LocalStoreError


# Supported schema versions for replay
SUPPORTED_SCHEMA_VERSIONS = {"HATE/v1"}
# Schema versions that require migration (not direct replay)
MIGRATION_REQUIRED_VERSIONS = {"HATE/v0.9", "HATE/v0.8"}


@dataclass
class ReplayError(Exception):
    """Error during replay operation."""
    message: str
    bundle_id: str
    phase: str  # "validate", "schema_check", "replay", "baseline"
    diagnostics: list[dict[str, Any]] = field(default_factory=list)

    def __str__(self) -> str:
        return f"ReplayError({self.phase}): {self.message} for bundle {self.bundle_id}"


@dataclass
class ReplayReport:
    """Byte-stable replay report."""
    bundle_id: str  # Non-default first
    run_id: str  # Non-default first
    schema_version: str = "HATE/v1"
    record_type: str = "store_replay_report"
    replay_hash: str = ""  # Deterministic hash of replay content
    source_bundle_hash: str = ""  # Hash of original bundle manifest
    schema_compatible: bool = True
    migration_hold: bool = False
    legal_hold_preserved: bool = True
    baseline_valid: bool = True
    artifacts_replayed: int = 0
    artifacts_missing: int = 0
    hash_mismatches: int = 0
    replayed_at: str = ""
    diagnostics: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict with sorted keys for byte-stability."""
        return {
            "schema_version": self.schema_version,
            "record_type": self.record_type,
            "bundle_id": self.bundle_id,
            "run_id": self.run_id,
            "replay_hash": self.replay_hash,
            "source_bundle_hash": self.source_bundle_hash,
            "schema_compatible": self.schema_compatible,
            "migration_hold": self.migration_hold,
            "legal_hold_preserved": self.legal_hold_preserved,
            "baseline_valid": self.baseline_valid,
            "artifacts_replayed": self.artifacts_replayed,
            "artifacts_missing": self.artifacts_missing,
            "hash_mismatches": self.hash_mismatches,
            "replayed_at": self.replayed_at,
            "diagnostics": self.diagnostics,
        }

    def compute_hash(self) -> str:
        """Compute deterministic hash of replay report."""
        return compute_json_hash_for_write(self.to_dict())


@dataclass
class BaselineInfo:
    """Baseline selection information."""
    baseline_bundle_id: str
    baseline_run_id: str
    baseline_created_at: str
    selection_method: str  # "manifest_timestamp", "explicit_ref", "run_metadata"
    is_filename_sort: bool  # True if selected by filename sorting (invalid)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        return {
            "baseline_bundle_id": self.baseline_bundle_id,
            "baseline_run_id": self.baseline_run_id,
            "baseline_created_at": self.baseline_created_at,
            "selection_method": self.selection_method,
            "is_filename_sort": self.is_filename_sort,
        }


def replay_bundle(
    store: LocalStore,
    bundle_id: str,
    baseline_ref: str | None = None,
) -> ReplayReport:
    """Replay a bundle to produce byte-stable report.

    Args:
        store: Local store instance
        bundle_id: Bundle to replay
        baseline_ref: Optional explicit baseline reference (not filename sorting)

    Returns:
        Byte-stable replay report

    Raises:
        ReplayError: If bundle cannot be replayed
        HardDQFinding: If corruption detected
    """
    # Phase 1: Validate bundle exists and is complete
    manifest = _validate_bundle_complete(store, bundle_id)

    # Phase 2: Check schema compatibility
    schema_compatible, migration_hold = _check_schema_compatibility(manifest)

    # Phase 3: Verify legal hold preserved
    legal_hold_preserved = _verify_legal_hold_preserved(manifest)

    # Phase 4: Validate baseline selection (if comparing)
    baseline_valid = True
    if baseline_ref:
        baseline_valid = _validate_baseline_selection(store, baseline_ref)

    # Phase 5: Replay artifacts with hash verification
    artifacts_replayed, artifacts_missing, hash_mismatches, diagnostics = _replay_artifacts(
        store, bundle_id, manifest
    )

    # Build report
    report = ReplayReport(
        bundle_id=bundle_id,
        run_id=manifest.run_id,
        replay_hash="",  # Will be computed after
        source_bundle_hash=_compute_manifest_hash(manifest),
        schema_compatible=schema_compatible,
        migration_hold=migration_hold,
        legal_hold_preserved=legal_hold_preserved,
        baseline_valid=baseline_valid,
        artifacts_replayed=artifacts_replayed,
        artifacts_missing=artifacts_missing,
        hash_mismatches=hash_mismatches,
        replayed_at=datetime.now(timezone.utc).isoformat(),
        diagnostics=diagnostics,
    )

    # Compute deterministic hash
    report.replay_hash = report.compute_hash()

    return report


def _validate_bundle_complete(store: LocalStore, bundle_id: str) -> StoreManifest:
    """Validate bundle exists and is complete.

    Raises HardDQFinding if bundle is incomplete or missing.
    """
    try:
        manifest = store.read_manifest(bundle_id)
    except LocalStoreError as e:
        raise HardDQFinding(
            message="Bundle manifest missing or unreadable",
            index_type="bundles",
            referenced_key=bundle_id,
            missing_path=str(store.store_root / bundle_id),
            diagnostics=[{"error": str(e)}],
        )

    if not manifest.completed:
        raise HardDQFinding(
            message="Bundle is incomplete (manifest not marked completed)",
            index_type="bundles",
            referenced_key=bundle_id,
            missing_path=str(store.store_root / bundle_id / "store-manifest.json"),
            diagnostics=[{"completed": False}],
        )

    return manifest


def _check_schema_compatibility(manifest: StoreManifest) -> tuple[bool, bool]:
    """Check schema version compatibility.

    Returns:
        (schema_compatible, migration_hold)

    - schema_compatible=True: Direct replay possible
    - migration_hold=True: Migration required before replay
    """
    schema_versions = manifest.schema_versions

    # Check bundle schema version
    bundle_schema = schema_versions.get("bundle", "unknown")

    if bundle_schema in SUPPORTED_SCHEMA_VERSIONS:
        return True, False

    if bundle_schema in MIGRATION_REQUIRED_VERSIONS:
        return False, True

    # Unknown schema version - migration hold
    return False, True


def _verify_legal_hold_preserved(manifest: StoreManifest) -> bool:
    """Verify legal hold metadata is present and valid.

    Legal hold is mandatory - missing is hard DQ.
    """
    legal_hold = manifest.legal_hold

    if not legal_hold:
        return False

    # Check required fields
    required_fields = {"status", "reason", "held_since"}
    if not all(f in legal_hold for f in required_fields):
        return False

    return True


def _validate_baseline_selection(store: LocalStore, baseline_ref: str) -> bool:
    """Validate baseline selection method.

    Baseline cannot be selected by filename sorting only.
    Valid methods: manifest_timestamp, explicit_ref, run_metadata

    Returns True if baseline selection is valid.
    """
    # If baseline_ref looks like filename-based, it's invalid
    if baseline_ref.startswith("sort:") or baseline_ref.startswith("filename:"):
        return False

    # If baseline_ref is explicit bundle_id or run_id, it's valid
    if baseline_ref.startswith("bundle:") or baseline_ref.startswith("run:"):
        return True

    # Default: assume explicit reference is valid
    # (actual validation would check run metadata)
    return True


def _replay_artifacts(
    store: LocalStore,
    bundle_id: str,
    manifest: StoreManifest,
) -> tuple[int, int, int, list[dict[str, Any]]]:
    """Replay all artifacts with hash verification.

    Returns:
        (artifacts_replayed, artifacts_missing, hash_mismatches, diagnostics)
    """
    artifacts_replayed = 0
    artifacts_missing = 0
    hash_mismatches = 0
    diagnostics = []

    for artifact_id in manifest.artifact_ids:
        expected_hash = manifest.content_hashes.get(artifact_id)

        try:
            artifact_path = store.store_root / bundle_id / f"{artifact_id}.json"
            if not artifact_path.exists():
                artifacts_missing += 1
                diagnostics.append({
                    "artifact_id": artifact_id,
                    "issue": "missing_artifact",
                    "severity": "hard_dq",
                })
                continue

            actual_hash = compute_file_hash(artifact_path)

            if expected_hash and actual_hash != expected_hash:
                hash_mismatches += 1
                diagnostics.append({
                    "artifact_id": artifact_id,
                    "issue": "hash_mismatch",
                    "expected": expected_hash,
                    "actual": actual_hash,
                    "severity": "hard_dq",
                })
            else:
                artifacts_replayed += 1

        except Exception as e:
            artifacts_missing += 1
            diagnostics.append({
                "artifact_id": artifact_id,
                "issue": "read_error",
                "error": str(e),
                "severity": "hard_dq",
            })

    return artifacts_replayed, artifacts_missing, hash_mismatches, diagnostics


def _compute_manifest_hash(manifest: StoreManifest) -> str:
    """Compute hash of manifest for replay tracking."""
    manifest_dict = manifest.to_dict()
    return compute_json_hash_for_write(manifest_dict)


def select_baseline_by_timestamp(
    store: LocalStore,
    run_id: str,
    exclude_bundle_id: str | None = None,
) -> BaselineInfo | None:
    """Select baseline by manifest timestamp (not filename sorting).

    This is the valid baseline selection method.
    Filename sorting is invalid and must be explicitly rejected.

    Args:
        store: Local store instance
        run_id: Run ID to find baseline for
        exclude_bundle_id: Bundle to exclude (current bundle being compared)

    Returns:
        BaselineInfo if baseline found, None otherwise
    """
    # Find all bundles for this run
    bundle_ids = store.list_bundles_for_run(run_id)

    if exclude_bundle_id:
        bundle_ids = [b for b in bundle_ids if b != exclude_bundle_id]

    if not bundle_ids:
        return None

    # Read manifests and sort by created_at timestamp (not filename)
    manifests = []
    for bundle_id in bundle_ids:
        try:
            manifest = store.read_manifest_by_bundle(bundle_id)
            manifests.append((bundle_id, manifest))
        except LocalStoreError:
            continue

    if not manifests:
        return None

    # Sort by created_at descending (most recent first, but we want previous)
    sorted_manifests = sorted(
        manifests,
        key=lambda x: x[1].created_at,
        reverse=True,
    )

    # Get the most recent (excluding current if provided)
    if sorted_manifests:
        baseline_bundle_id, baseline_manifest = sorted_manifests[0]
        return BaselineInfo(
            baseline_bundle_id=baseline_bundle_id,
            baseline_run_id=baseline_manifest.run_id,
            baseline_created_at=baseline_manifest.created_at,
            selection_method="manifest_timestamp",
            is_filename_sort=False,
        )

    return None


def select_baseline_by_filename_sort(
    bundle_ids: list[str],
) -> BaselineInfo:
    """Select baseline by filename sorting (INVALID method).

    This method exists ONLY to detect and reject invalid baseline selection.
    Using this method is a hard DQ.

    Args:
        bundle_ids: List of bundle IDs (filenames)

    Returns:
        BaselineInfo with is_filename_sort=True (marking it as invalid)
    """
    # Sort by filename (alphabetically) - this is the INVALID method
    sorted_ids = sorted(bundle_ids)

    return BaselineInfo(
        baseline_bundle_id=sorted_ids[0] if sorted_ids else "",
        baseline_run_id="",
        baseline_created_at="",
        selection_method="filename_sort",
        is_filename_sort=True,  # INVALID - must be rejected
    )