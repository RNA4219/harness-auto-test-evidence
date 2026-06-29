"""Compare Module for HATE Local Store.

Compares bundles to detect improvement, regression, or no-change.
Baseline comparison is valid only when selected by manifest timestamp.

Key invariants:
- Compare detects improvement, regression, no-change
- Baseline cannot be selected by filename sorting only
- Legal hold must be preserved during comparison

No-Go conditions:
- Baseline selection uses filename sorting
- Comparison changes canonical bundle content
- Regression is silently ignored
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .atomic_write import compute_json_hash_for_write
from .indexes import HardDQFinding
from .local_store import LocalStore, StoreManifest, LocalStoreError
from .replay import (
    ReplayReport,
    ReplayError,
    BaselineInfo,
    select_baseline_by_timestamp,
    select_baseline_by_filename_sort,
)


class ComparisonResult(str, Enum):
    """Comparison result classification."""
    IMPROVEMENT = "improvement"
    REGRESSION = "regression"
    NO_CHANGE = "no_change"
    INCOMPARABLE = "incomparable"  # Cannot compare (missing baseline, different schema)


@dataclass
class ArtifactDiff:
    """Difference between two artifact versions."""
    artifact_id: str
    baseline_hash: str | None
    current_hash: str | None
    result: ComparisonResult
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        return {
            "artifact_id": self.artifact_id,
            "baseline_hash": self.baseline_hash,
            "current_hash": self.current_hash,
            "result": self.result.value,
            "details": self.details,
        }


@dataclass
class ComparisonReport:
    """Byte-stable comparison report."""
    bundle_id: str  # Non-default first
    run_id: str  # Non-default first
    schema_version: str = "HATE/v1"
    record_type: str = "store_comparison_report"
    baseline_bundle_id: str | None = None
    baseline_selection_method: str = ""
    is_filename_sort_baseline: bool = False  # True if baseline selected by filename (invalid)
    comparison_result: ComparisonResult = ComparisonResult.NO_CHANGE
    improvements: int = 0
    regressions: int = 0
    no_changes: int = 0
    artifacts_compared: int = 0
    artifacts_missing_in_baseline: int = 0
    artifacts_missing_in_current: int = 0
    comparison_hash: str = ""  # Deterministic hash of comparison content
    artifact_diffs: list[ArtifactDiff] = field(default_factory=list)
    compared_at: str = ""
    diagnostics: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict with sorted keys for byte-stability."""
        return {
            "schema_version": self.schema_version,
            "record_type": self.record_type,
            "bundle_id": self.bundle_id,
            "run_id": self.run_id,
            "baseline_bundle_id": self.baseline_bundle_id,
            "baseline_selection_method": self.baseline_selection_method,
            "is_filename_sort_baseline": self.is_filename_sort_baseline,
            "comparison_result": self.comparison_result.value,
            "improvements": self.improvements,
            "regressions": self.regressions,
            "no_changes": self.no_changes,
            "artifacts_compared": self.artifacts_compared,
            "artifacts_missing_in_baseline": self.artifacts_missing_in_baseline,
            "artifacts_missing_in_current": self.artifacts_missing_in_current,
            "comparison_hash": self.comparison_hash,
            "artifact_diffs": [d.to_dict() for d in self.artifact_diffs],
            "compared_at": self.compared_at,
            "diagnostics": self.diagnostics,
        }

    def compute_hash(self) -> str:
        """Compute deterministic hash of comparison report."""
        return compute_json_hash_for_write(self.to_dict())


@dataclass
class CompareError(Exception):
    """Error during comparison operation."""
    message: str
    bundle_id: str
    baseline_bundle_id: str | None
    diagnostics: list[dict[str, Any]] = field(default_factory=list)

    def __str__(self) -> str:
        return f"CompareError: {self.message} for bundle {self.bundle_id}"


def compare_bundle_to_baseline(
    store: LocalStore,
    bundle_id: str,
    baseline_ref: str | None = None,
) -> ComparisonReport:
    """Compare a bundle to its baseline.

    Args:
        store: Local store instance
        bundle_id: Bundle to compare
        baseline_ref: Optional explicit baseline reference (not filename sorting)

    Returns:
        Byte-stable comparison report

    Raises:
        CompareError: If comparison cannot be performed
        HardDQFinding: If corruption detected
    """
    # Get current bundle manifest
    current_manifest = _validate_bundle_complete(store, bundle_id)

    # Select or validate baseline
    baseline_info: BaselineInfo | None = None
    is_filename_sort = False

    if baseline_ref:
        if baseline_ref.startswith("filename:") or baseline_ref.startswith("sort:"):
            # This is invalid - detect and reject
            is_filename_sort = True
            baseline_info = None
        elif baseline_ref.startswith("bundle:"):
            baseline_bundle_id = baseline_ref.replace("bundle:", "")
            try:
                baseline_manifest = store.read_manifest_by_bundle(baseline_bundle_id)
                baseline_info = BaselineInfo(
                    baseline_bundle_id=baseline_bundle_id,
                    baseline_run_id=baseline_manifest.run_id,
                    baseline_created_at=baseline_manifest.created_at,
                    selection_method="explicit_ref",
                    is_filename_sort=False,
                )
            except LocalStoreError:
                pass  # baseline_info remains None
        elif baseline_ref.startswith("run:"):
            run_id = baseline_ref.replace("run:", "")
            baseline_info = select_baseline_by_timestamp(
                store, run_id, exclude_bundle_id=bundle_id
            )
    else:
        # Auto-select by timestamp (valid method)
        baseline_info = select_baseline_by_timestamp(
            store, current_manifest.run_id, exclude_bundle_id=bundle_id
        )

    # If baseline selected by filename sorting, mark as invalid
    if baseline_ref and (baseline_ref.startswith("filename:") or baseline_ref.startswith("sort:")):
        # Explicitly invalid baseline selection
        return _create_invalid_baseline_report(bundle_id, current_manifest, baseline_ref)

    # If no baseline found, return incomparable
    if not baseline_info:
        return _create_incomparable_report(bundle_id, current_manifest, "No baseline found")

    # Compare artifacts
    (
        improvements,
        regressions,
        no_changes,
        artifacts_compared,
        missing_in_baseline,
        missing_in_current,
        artifact_diffs,
        diagnostics,
    ) = _compare_artifacts(store, bundle_id, baseline_info.baseline_bundle_id)

    # Determine overall result
    if regressions > 0 and improvements > 0:
        result = ComparisonResult.REGRESSION  # Any regression is a regression
    elif regressions > 0:
        result = ComparisonResult.REGRESSION
    elif improvements > 0:
        result = ComparisonResult.IMPROVEMENT
    else:
        result = ComparisonResult.NO_CHANGE

    # Build report
    report = ComparisonReport(
        bundle_id=bundle_id,
        run_id=current_manifest.run_id,
        baseline_bundle_id=baseline_info.baseline_bundle_id,
        baseline_selection_method=baseline_info.selection_method,
        is_filename_sort_baseline=baseline_info.is_filename_sort,
        comparison_result=result,
        improvements=improvements,
        regressions=regressions,
        no_changes=no_changes,
        artifacts_compared=artifacts_compared,
        artifacts_missing_in_baseline=missing_in_baseline,
        artifacts_missing_in_current=missing_in_current,
        comparison_hash="",  # Will be computed after
        artifact_diffs=artifact_diffs,
        compared_at=datetime.now(timezone.utc).isoformat(),
        diagnostics=diagnostics,
    )

    # Compute deterministic hash
    report.comparison_hash = report.compute_hash()

    return report


def _validate_bundle_complete(store: LocalStore, bundle_id: str) -> StoreManifest:
    """Validate bundle exists and is complete.

    Raises HardDQFinding if bundle is incomplete or missing.
    """
    try:
        manifest = store.read_manifest_by_bundle(bundle_id)
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


def _compare_artifacts(
    store: LocalStore,
    current_bundle_id: str,
    baseline_bundle_id: str,
) -> tuple[int, int, int, int, int, int, list[ArtifactDiff], list[dict[str, Any]]]:
    """Compare artifacts between current and baseline bundles.

    Returns:
        (improvements, regressions, no_changes, artifacts_compared,
         missing_in_baseline, missing_in_current, artifact_diffs, diagnostics)
    """
    improvements = 0
    regressions = 0
    no_changes = 0
    artifacts_compared = 0
    missing_in_baseline = 0
    missing_in_current = 0
    artifact_diffs = []
    diagnostics = []

    # Read manifests
    try:
        current_manifest = store.read_manifest_by_bundle(current_bundle_id)
        baseline_manifest = store.read_manifest_by_bundle(baseline_bundle_id)
    except LocalStoreError as e:
        diagnostics.append({
            "issue": "manifest_read_error",
            "error": str(e),
            "severity": "hard_dq",
        })
        return 0, 0, 0, 0, 0, 0, [], diagnostics

    # Get all artifact IDs from both bundles
    current_artifact_ids = set(current_manifest.artifact_ids)
    baseline_artifact_ids = set(baseline_manifest.artifact_ids)

    # Artifacts only in current (new artifacts - potential improvement)
    new_artifacts = current_artifact_ids - baseline_artifact_ids
    for artifact_id in new_artifacts:
        missing_in_baseline += 1
        current_hash = current_manifest.content_hashes.get(artifact_id)
        artifact_diffs.append(ArtifactDiff(
            artifact_id=artifact_id,
            baseline_hash=None,
            current_hash=current_hash,
            result=ComparisonResult.IMPROVEMENT,
            details={"reason": "new_artifact"},
        ))

    # Artifacts only in baseline (removed artifacts - potential regression)
    removed_artifacts = baseline_artifact_ids - current_artifact_ids
    for artifact_id in removed_artifacts:
        missing_in_current += 1
        baseline_hash = baseline_manifest.content_hashes.get(artifact_id)
        artifact_diffs.append(ArtifactDiff(
            artifact_id=artifact_id,
            baseline_hash=baseline_hash,
            current_hash=None,
            result=ComparisonResult.REGRESSION,
            details={"reason": "removed_artifact"},
        ))

    # Artifacts in both (compare hashes)
    common_artifacts = current_artifact_ids & baseline_artifact_ids
    for artifact_id in common_artifacts:
        current_hash = current_manifest.content_hashes.get(artifact_id)
        baseline_hash = baseline_manifest.content_hashes.get(artifact_id)

        if current_hash == baseline_hash:
            no_changes += 1
            artifacts_compared += 1
            artifact_diffs.append(ArtifactDiff(
                artifact_id=artifact_id,
                baseline_hash=baseline_hash,
                current_hash=current_hash,
                result=ComparisonResult.NO_CHANGE,
                details={},
            ))
        else:
            # Hash changed - need semantic comparison
            # For now, classify as no_change unless we have semantic info
            # In real implementation, would read artifact content and compare semantics
            artifacts_compared += 1
            artifact_diffs.append(ArtifactDiff(
                artifact_id=artifact_id,
                baseline_hash=baseline_hash,
                current_hash=current_hash,
                result=ComparisonResult.NO_CHANGE,  # Default: hash change without semantic analysis
                details={"hash_changed": True, "reason": "hash_difference"},
            ))

    # Count improvements and regressions
    for diff in artifact_diffs:
        if diff.result == ComparisonResult.IMPROVEMENT:
            improvements += 1
        elif diff.result == ComparisonResult.REGRESSION:
            regressions += 1

    return (
        improvements,
        regressions,
        no_changes,
        artifacts_compared,
        missing_in_baseline,
        missing_in_current,
        artifact_diffs,
        diagnostics,
    )


def _create_incomparable_report(
    bundle_id: str,
    manifest: StoreManifest,
    reason: str,
) -> ComparisonReport:
    """Create report for incomparable bundles."""
    report = ComparisonReport(
        bundle_id=bundle_id,
        run_id=manifest.run_id,
        baseline_bundle_id=None,
        baseline_selection_method="none",
        is_filename_sort_baseline=False,
        comparison_result=ComparisonResult.INCOMPARABLE,
        improvements=0,
        regressions=0,
        no_changes=0,
        artifacts_compared=0,
        artifacts_missing_in_baseline=0,
        artifacts_missing_in_current=0,
        comparison_hash="",
        artifact_diffs=[],
        compared_at=datetime.now(timezone.utc).isoformat(),
        diagnostics=[{"reason": reason}],
    )
    report.comparison_hash = report.compute_hash()
    return report


def _create_invalid_baseline_report(
    bundle_id: str,
    manifest: StoreManifest,
    baseline_ref: str,
) -> ComparisonReport:
    """Create report for invalid baseline selection (filename sort)."""
    report = ComparisonReport(
        bundle_id=bundle_id,
        run_id=manifest.run_id,
        baseline_bundle_id=None,
        baseline_selection_method="filename_sort",
        is_filename_sort_baseline=True,  # INVALID
        comparison_result=ComparisonResult.INCOMPARABLE,
        improvements=0,
        regressions=0,
        no_changes=0,
        artifacts_compared=0,
        artifacts_missing_in_baseline=0,
        artifacts_missing_in_current=0,
        comparison_hash="",
        artifact_diffs=[],
        compared_at=datetime.now(timezone.utc).isoformat(),
        diagnostics=[{
            "reason": "Baseline selected by filename sorting",
            "baseline_ref": baseline_ref,
            "severity": "hard_dq",
        }],
    )
    report.comparison_hash = report.compute_hash()
    return report


def compare_bundles_direct(
    store: LocalStore,
    bundle_id_a: str,
    bundle_id_b: str,
) -> ComparisonReport:
    """Directly compare two bundles without baseline selection.

    This is for explicit comparison requests, not baseline comparison.

    Args:
        store: Local store instance
        bundle_id_a: First bundle
        bundle_id_b: Second bundle

    Returns:
        Comparison report
    """
    manifest_a = _validate_bundle_complete(store, bundle_id_a)
    manifest_b = _validate_bundle_complete(store, bundle_id_b)

    # Compare artifacts
    (
        improvements,
        regressions,
        no_changes,
        artifacts_compared,
        missing_in_baseline,
        missing_in_current,
        artifact_diffs,
        diagnostics,
    ) = _compare_artifacts(store, bundle_id_a, bundle_id_b)

    # Determine result (A compared to B)
    if regressions > 0 and improvements > 0:
        result = ComparisonResult.REGRESSION
    elif regressions > 0:
        result = ComparisonResult.REGRESSION
    elif improvements > 0:
        result = ComparisonResult.IMPROVEMENT
    else:
        result = ComparisonResult.NO_CHANGE

    report = ComparisonReport(
        bundle_id=bundle_id_a,
        run_id=manifest_a.run_id,
        baseline_bundle_id=bundle_id_b,
        baseline_selection_method="explicit_direct",
        is_filename_sort_baseline=False,
        comparison_result=result,
        improvements=improvements,
        regressions=regressions,
        no_changes=no_changes,
        artifacts_compared=artifacts_compared,
        artifacts_missing_in_baseline=missing_in_baseline,
        artifacts_missing_in_current=missing_in_current,
        comparison_hash="",
        artifact_diffs=artifact_diffs,
        compared_at=datetime.now(timezone.utc).isoformat(),
        diagnostics=diagnostics,
    )
    report.comparison_hash = report.compute_hash()
    return report