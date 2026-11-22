"""保存コピーを検証し、同じ証跡項目の結果を比較する。"""

from __future__ import annotations

from datetime import UTC, datetime

from .artifact_compare import ComparisonStats, compare_manifest_artifacts, failed_comparison
from .compare_models import ArtifactDiff as ArtifactDiff
from .compare_models import CompareError as CompareError
from .compare_models import ComparisonReport as ComparisonReport
from .compare_models import ComparisonResult as ComparisonResult
from .compatibility import manifest_schema_findings
from .indexes import HardDQFinding, IndexLookupError
from .integrity import verify_bundle_copy
from .local_store import LocalStore, LocalStoreError, StoreManifest
from .locking import store_operation
from .replay import BaselineInfo, select_baseline_by_timestamp
from .replay import _validate_bundle_complete as _validate_bundle_complete
from .report_serialization import relative_diagnostics


def _copy_diagnostics(store: LocalStore, manifest: StoreManifest, side: str) -> list[dict[str, object]]:
    directory = store.store_root / "runs" / manifest.run_id / manifest.bundle_id
    return relative_diagnostics([
        {**item, "side": side, "run_id": manifest.run_id, "bundle_id": manifest.bundle_id, "severity": "hard_dq"}
        for item in verify_bundle_copy(directory, manifest)
    ], store.store_root)


def _compare_artifacts(
    store: LocalStore, current_bundle_id: str, baseline_bundle_id: str, *,
    current_run_id: str | None = None, baseline_run_id: str | None = None,
) -> ComparisonStats:
    try:
        current = _validate_bundle_complete(store, current_bundle_id, run_id=current_run_id)
        baseline = _validate_bundle_complete(store, baseline_bundle_id, run_id=baseline_run_id)
    except (LocalStoreError, IndexLookupError, HardDQFinding, OSError) as exc:
        return failed_comparison([{"issue": "manifest_read_error", "error": str(exc), "severity": "hard_dq"}])
    diagnostics = _copy_diagnostics(store, current, "current") + _copy_diagnostics(store, baseline, "baseline")
    if diagnostics:
        return failed_comparison(diagnostics)
    unsupported = [
        {**item, "issue": "unsupported_comparison_schema", "side": side, "severity": "soft_dq"}
        for side, manifest in (("current", current), ("baseline", baseline))
        for item in manifest_schema_findings(manifest)
    ]
    if unsupported:
        return failed_comparison(unsupported)
    return compare_manifest_artifacts(store.store_root, current, baseline)


def _report(
    manifest: StoreManifest, baseline: BaselineInfo | None, stats: ComparisonStats, *, filename_sort: bool = False,
) -> ComparisonReport:
    improvements, regressions, no_changes, paired, added, removed, diffs, diagnostics = stats
    if diagnostics or baseline is None:
        result = ComparisonResult.INCOMPARABLE
    elif regressions:
        result = ComparisonResult.REGRESSION
    elif any(item.result == ComparisonResult.INCOMPARABLE for item in diffs):
        result = ComparisonResult.INCOMPARABLE
    elif improvements:
        result = ComparisonResult.IMPROVEMENT
    else:
        result = ComparisonResult.NO_CHANGE
    report = ComparisonReport(
        bundle_id=manifest.bundle_id, run_id=manifest.run_id,
        baseline_bundle_id=baseline.baseline_bundle_id if baseline else None,
        baseline_run_id=baseline.baseline_run_id if baseline else "",
        baseline_selection_method=baseline.selection_method if baseline else ("filename_sort" if filename_sort else "none"),
        is_filename_sort_baseline=filename_sort, comparison_result=result,
        improvements=improvements, regressions=regressions, no_changes=no_changes,
        artifacts_compared=paired, artifacts_missing_in_baseline=added, artifacts_missing_in_current=removed,
        artifact_diffs=diffs, diagnostics=diagnostics, compared_at=datetime.now(UTC).isoformat(),
    )
    report.comparison_hash = report.compute_hash()
    return report


def _info(manifest: StoreManifest, method: str) -> BaselineInfo:
    return BaselineInfo(manifest.bundle_id, manifest.run_id, manifest.created_at, method, False)


@store_operation
def compare_bundle_to_baseline(
    store: LocalStore, bundle_id: str, baseline_ref: str | None = None, *, run_id: str | None = None,
) -> ComparisonReport:
    """runを指定するとその保存コピーを使用する。省略時はbundle索引aliasを使う。"""
    current = _validate_bundle_complete(store, bundle_id, run_id=run_id)
    diagnostics = _copy_diagnostics(store, current, "current")
    if diagnostics:
        return _report(current, None, failed_comparison(diagnostics))
    baseline: BaselineInfo | None = None
    if baseline_ref is not None and baseline_ref.startswith(("sort:", "filename:")):
        return _report(current, None, failed_comparison([
            {"issue": "invalid_baseline_selection", "baseline_ref": baseline_ref, "severity": "hard_dq"},
        ]), filename_sort=True)
    try:
        if baseline_ref is None:
            baseline = select_baseline_by_timestamp(
                store, current.run_id, exclude_bundle_id=bundle_id, before_created_at=current.created_at,
            )
        elif baseline_ref.startswith("bundle:") and baseline_ref.split(":", 1)[1]:
            selected = _validate_bundle_complete(store, baseline_ref.split(":", 1)[1])
            baseline = _info(selected, "explicit_ref")
        elif baseline_ref.startswith("run:") and baseline_ref.split(":", 1)[1]:
            selected_run = baseline_ref.split(":", 1)[1]
            baseline = select_baseline_by_timestamp(
                store, selected_run, exclude_bundle_id=bundle_id if selected_run == current.run_id else None,
                before_created_at=current.created_at if selected_run == current.run_id else None,
            )
        else:
            raise ValueError("Unsupported or empty baseline reference")
    except (LocalStoreError, IndexLookupError, HardDQFinding, OSError, ValueError) as exc:
        return _report(current, None, failed_comparison(relative_diagnostics([
            {"issue": "baseline_unreadable", "error": str(exc), "severity": "hard_dq", "validation": getattr(exc, "diagnostics", [])},
        ], store.store_root)))
    if baseline is None:
        return _report(current, None, failed_comparison([
            {"issue": "baseline_not_found", "severity": "hard_dq" if baseline_ref is not None else "soft_dq"},
        ]))
    stats = _compare_artifacts(
        store, bundle_id, baseline.baseline_bundle_id,
        current_run_id=current.run_id, baseline_run_id=baseline.baseline_run_id,
    )
    return _report(current, baseline, stats)


@store_operation
def compare_bundles_direct(
    store: LocalStore, bundle_id_a: str, bundle_id_b: str, *,
    run_id_a: str | None = None, run_id_b: str | None = None,
) -> ComparisonReport:
    """Aをcurrent、Bをbaselineとして、それぞれ指定runのコピーを比較する。"""
    current = _validate_bundle_complete(store, bundle_id_a, run_id=run_id_a)
    baseline = _validate_bundle_complete(store, bundle_id_b, run_id=run_id_b)
    stats = _compare_artifacts(
        store, bundle_id_a, bundle_id_b, current_run_id=current.run_id, baseline_run_id=baseline.run_id,
    )
    return _report(current, _info(baseline, "explicit_direct"), stats)
