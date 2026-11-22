"""Replay Module for HATE Local Store.

Verifies stored bundle contents and produces reproducible replay evidence.
Execution time remains available as observation metadata, outside the default
canonical report and its hash.

Key invariants:
- Stored bundle and artifact corruption must not be reported as replay success
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

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .atomic_write import (
    compute_json_hash,
)
from .compatibility import MIGRATION_REQUIRED_VERSIONS as MIGRATION_REQUIRED_VERSIONS
from .compatibility import SUPPORTED_SCHEMA_VERSIONS as SUPPORTED_SCHEMA_VERSIONS
from .compatibility import manifest_schema_findings
from .indexes import HardDQFinding, IndexLookupError
from .integrity import verify_bundle_copy
from .local_store import LocalStore, LocalStoreError, StoreManifest
from .locking import store_operation
from .replay_report import build_store_replay_report as build_store_replay_report
from .report_serialization import relative_diagnostics, report_data, report_hash
from .timestamps import timestamp_key


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
    """Replay validation results and execution metadata."""
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
    integrity_ok: bool = True
    baseline_resolution: dict[str, Any] | None = None

    def to_dict(self, *, include_observation: bool = False) -> dict[str, Any]:
        """Convert validation results to a serializable dictionary."""
        data = {
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
            "integrity_ok": self.integrity_ok,
        }
        if self.baseline_resolution is not None:
            data["baseline_resolution"] = self.baseline_resolution
        return report_data(data, observation_field="replayed_at", include_observation=include_observation)

    def compute_hash(self) -> str:
        """Compute deterministic hash of replay report."""
        return report_hash(self.to_dict(), hash_field="replay_hash", observation_field="replayed_at")




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


@store_operation
def replay_bundle(
    store: LocalStore,
    bundle_id: str,
    baseline_ref: str | None = None,
    *,
    run_id: str | None = None,
) -> ReplayReport:
    """Replay a stored bundle with integrity and baseline validation.

    Args:
        store: Local store instance
        bundle_id: Bundle to replay
        baseline_ref: Optional explicit baseline reference (not filename sorting)

    Returns:
        Replay validation report

    Raises:
        ReplayError: If bundle cannot be replayed
        HardDQFinding: If corruption detected
    """
    # Phase 1: Validate bundle exists and is complete
    manifest = _validate_bundle_complete(store, bundle_id, run_id=run_id)

    # Phase 2: Check schema compatibility
    schema_compatible, migration_hold = _check_schema_compatibility(manifest)

    # Phase 3: Verify legal hold preserved
    legal_hold_preserved = _verify_legal_hold_preserved(manifest)

    # Phase 4: Validate baseline selection (if comparing)
    baseline_resolution = None
    baseline_diagnostics: list[dict[str, Any]] = []
    if baseline_ref is not None:
        baseline_resolution, baseline_diagnostics = _resolve_baseline(store, baseline_ref)
    baseline_valid = baseline_resolution is None or baseline_resolution["valid"] is True
    if any(item["issue"] == "baseline_store_schema_version_unsupported" for item in baseline_diagnostics):
        schema_compatible, migration_hold = False, True

    # Phase 5: Replay artifacts with hash verification
    artifacts_replayed, artifacts_missing, hash_mismatches, diagnostics = _replay_artifacts(
        store, bundle_id, manifest
    )
    integrity_ok = not diagnostics
    diagnostics.extend({**item, "side": "current", "severity": "soft_dq"} for item in manifest_schema_findings(manifest))
    diagnostics.extend(baseline_diagnostics)
    if not schema_compatible:
        artifacts_replayed = 0

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
        replayed_at=datetime.now(UTC).isoformat(),
        diagnostics=relative_diagnostics(diagnostics, store.store_root),
        integrity_ok=integrity_ok,
        baseline_resolution=baseline_resolution,
    )

    # Compute deterministic hash
    report.replay_hash = report.compute_hash()

    return report


def _validate_bundle_complete(store: LocalStore, bundle_id: str, *, run_id: str | None = None) -> StoreManifest:
    """Validate bundle exists and is complete.

    Raises HardDQFinding if bundle is incomplete or missing.
    """
    try:
        manifest = store.read_manifest_by_bundle(bundle_id, run_id=run_id)
    except (LocalStoreError, IndexLookupError, OSError) as e:
        path = getattr(e, "path", None) or (
            store.store_root / "runs" / run_id / bundle_id / "store-manifest.json"
            if run_id is not None else store.index_manager.bundles_index.index_path
        )
        raise HardDQFinding(
            message="Bundle manifest missing or unreadable",
            index_type="bundles",
            referenced_key=bundle_id,
            missing_path=str(path),
            diagnostics=[{"error": str(e)}],
        ) from e

    if not manifest.completed:
        raise HardDQFinding(
            message="Bundle is incomplete (manifest not marked completed)",
            index_type="bundles",
            referenced_key=bundle_id,
            missing_path=str(store.store_root / "runs" / manifest.run_id / bundle_id / "store-manifest.json"),
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
    compatible = not manifest_schema_findings(manifest)
    return compatible, not compatible


def _verify_legal_hold_preserved(manifest: StoreManifest) -> bool:
    """Verify legal hold metadata is present and valid.

    Legal hold is mandatory - missing is hard DQ.
    """
    legal_hold = manifest.legal_hold

    if not legal_hold:
        return False

    # Check required fields
    required_fields = {"status", "reason", "held_since", "authorized_by"}
    if not all(f in legal_hold for f in required_fields):
        return False

    return True


def _validate_baseline_selection(store: LocalStore, baseline_ref: str) -> bool:
    """Validate baseline selection method.

    Baseline cannot be selected by filename sorting only.
    Valid methods: manifest_timestamp, explicit_ref, run_metadata

    Returns True if baseline selection is valid.
    """
    resolution, _ = _resolve_baseline(store, baseline_ref)
    return resolution["valid"] is True


def _resolve_baseline(store: LocalStore, baseline_ref: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    resolution: dict[str, Any] = {
        "baseline_bundle_id": "", "baseline_run_id": "", "baseline_created_at": "",
        "selection_method": "explicit_ref", "is_filename_sort": False, "valid": False,
    }
    diagnostics: list[dict[str, Any]] = []
    if not isinstance(baseline_ref, str) or not baseline_ref.startswith(("bundle:", "run:")):
        resolution["is_filename_sort"] = isinstance(baseline_ref, str) and baseline_ref.startswith(("filename:", "sort:"))
        diagnostics.append({"issue": "invalid_baseline_reference", "severity": "hard_dq"})
        return resolution, diagnostics
    kind, identifier = baseline_ref.split(":", 1)
    try:
        if not identifier:
            raise ValueError("Baseline identifier is empty")
        if kind == "run":
            selected = select_baseline_by_timestamp(store, identifier)
            if selected is None:
                raise ValueError("No completed baseline found for run")
            manifest = store.read_manifest_by_bundle(selected.baseline_bundle_id, run_id=identifier)
            resolution["selection_method"] = selected.selection_method
        else:
            manifest = store.read_manifest_by_bundle(identifier)
        resolution.update(
            baseline_bundle_id=manifest.bundle_id, baseline_run_id=manifest.run_id,
            baseline_created_at=manifest.created_at,
        )
        bundle_dir = store.store_root / "runs" / manifest.run_id / manifest.bundle_id
        diagnostics = [
            {**item, "issue": "baseline_" + item["issue"], "severity": "hard_dq"}
            for item in verify_bundle_copy(bundle_dir, manifest)
        ]
        resolution["valid"] = not diagnostics
        diagnostics.extend(
            {**item, "issue": "baseline_" + item["issue"], "side": "baseline", "severity": "soft_dq"}
            for item in manifest_schema_findings(manifest)
        )
    except (LocalStoreError, IndexLookupError, HardDQFinding, OSError, ValueError) as exc:
        diagnostics.append({
            "issue": "baseline_unreadable", "error": str(exc), "severity": "hard_dq",
            "validation": getattr(exc, "diagnostics", []),
        })
    return resolution, diagnostics


def _replay_artifacts(
    store: LocalStore,
    bundle_id: str,
    manifest: StoreManifest,
) -> tuple[int, int, int, list[dict[str, Any]]]:
    """Replay all artifacts with hash verification.

    Returns:
        (artifacts_replayed, artifacts_missing, hash_mismatches, diagnostics)
    """
    bundle_dir = store.store_root / "runs" / manifest.run_id / bundle_id
    diagnostics = [{**item, "severity": "hard_dq"} for item in verify_bundle_copy(bundle_dir, manifest)]
    missing = {item["artifact_id"] for item in diagnostics if item["issue"] in {"missing_artifact", "artifact_unreadable"}}
    mismatched = {item["artifact_id"] for item in diagnostics if item["issue"] in {"hash_mismatch", "missing_artifact_hash", "unlisted_artifact_hash"}}
    invalid = {item["artifact_id"] for item in diagnostics if "artifact_id" in item}
    structural_failure = any("artifact_id" not in item for item in diagnostics)
    replayed = 0 if structural_failure else len(set(manifest.artifact_ids) - invalid)
    return replayed, len(missing), len(mismatched), diagnostics


def _compute_manifest_hash(manifest: StoreManifest) -> str:
    """Compute hash of manifest for replay tracking."""
    manifest_dict = manifest.to_dict()
    return compute_json_hash(manifest_dict)


@store_operation
def select_baseline_by_timestamp(
    store: LocalStore,
    run_id: str,
    exclude_bundle_id: str | None = None,
    *,
    before_created_at: str | None = None,
) -> BaselineInfo | None:
    """Select baseline by manifest timestamp (not filename sorting).

    This is the valid baseline selection method.
    Filename sorting is invalid and must be explicitly rejected.

    Args:
        store: Local store instance
        run_id: Run ID to find baseline for
        exclude_bundle_id: Bundle to exclude (current bundle being compared)
        before_created_at: Strict upper time bound for selecting prior history

    Returns:
        BaselineInfo if baseline found, None otherwise
    """
    run_path = store.store_root / "runs" / run_id
    limit = None if before_created_at is None else timestamp_key(
        before_created_at, operation="select_baseline", path=run_path, field="before_created_at",
    )
    bundle_ids = store.list_bundles_for_run(run_id)

    if exclude_bundle_id:
        bundle_ids = [b for b in bundle_ids if b != exclude_bundle_id]

    if not bundle_ids:
        return None

    candidates = []
    for bundle_id in bundle_ids:
        manifest = store.read_manifest_by_bundle(bundle_id, run_id=run_id)
        stamp = timestamp_key(
            manifest.created_at, operation="select_baseline", path=run_path / bundle_id / "store-manifest.json",
        )
        if limit is not None and stamp >= limit:
            continue
        candidates.append((stamp, manifest))

    if not candidates:
        return None

    latest = max(stamp for stamp, _ in candidates)
    matches = [manifest for stamp, manifest in candidates if stamp == latest]
    if len(matches) != 1:
        raise LocalStoreError(
            "baseline is ambiguous: equal manifest timestamps", "select_baseline", run_path,
            [{"issue": "ambiguous_baseline_timestamp", "candidates": [
                {"bundle_id": manifest.bundle_id, "created_at": manifest.created_at}
                for manifest in sorted(matches, key=lambda item: item.bundle_id)
            ]}],
        )
    selected = matches[0]
    return BaselineInfo(selected.bundle_id, selected.run_id, selected.created_at, "manifest_timestamp", False)


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
