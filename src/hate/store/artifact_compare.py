"""内容由来IDとは別に、証跡項目のIDと既知の結果指標を比較する。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .atomic_write import compute_json_hash
from .compare_models import ArtifactDiff, ComparisonResult
from .local_store import LocalStoreError, _read_object
from .models import ARTIFACT_KIND_ALIASES, StoreManifest

ComparisonStats = tuple[int, int, int, int, int, int, list[ArtifactDiff], list[dict[str, Any]]]
ArtifactRecords = dict[tuple[str, str], tuple[str, dict[str, Any]]]


def failed_comparison(diagnostics: list[dict[str, Any]]) -> ComparisonStats:
    return 0, 0, 0, 0, 0, 0, [], diagnostics


def _payload(node: dict[str, Any]) -> dict[str, Any]:
    for field in ("data", "payload"):
        if isinstance(node.get(field), dict):
            return dict(node[field])
    return node


def _records(root: Path, manifest: StoreManifest) -> ArtifactRecords:
    records: ArtifactRecords = {}
    directory = root / "runs" / manifest.run_id / manifest.bundle_id
    for artifact_id in sorted(set(manifest.artifact_ids)):
        path = directory / f"{artifact_id}.json"
        node = _read_object(path, "compare_artifact")
        kind = ARTIFACT_KIND_ALIASES.get(str(node.get("kind")), str(node.get("kind")))
        identifier = _payload(node).get("canonical_test_id") if kind == "test_result" else None
        identifier = identifier or node.get("id")
        identity = "id:" + identifier if isinstance(identifier, str) and identifier.strip() else "content:" + compute_json_hash(node)
        key = kind, identity
        if key in records:
            raise LocalStoreError(
                "Multiple artifacts have the same comparison identity", "compare_artifact", path,
                [{"issue": "duplicate_artifact_identity", "kind": kind, "identity": identity}],
            )
        records[key] = artifact_id, node
    return records


def _status_value(kind: str, data: dict[str, Any]) -> int | None:
    value = data.get("status", data.get("outcome"))
    if not isinstance(value, str):
        return None
    if kind in {"test_result", "contract_evidence"}:
        return {"passed": 1, "pass": 1, "failed": 0, "fail": 0, "error": 0}.get(value)
    if kind == "mutation_evidence":
        return {"killed": 1, "survived": 0}.get(value)
    return None


def _direction(before: float, after: float) -> ComparisonResult:
    if after > before:
        return ComparisonResult.IMPROVEMENT
    if after < before:
        return ComparisonResult.REGRESSION
    return ComparisonResult.NO_CHANGE


def _coverage(before: dict[str, Any], after: dict[str, Any]) -> ComparisonResult | None:
    if "coverage_percent" in before and "coverage_percent" in after:
        values = [before["coverage_percent"], after["coverage_percent"]]
        if all(isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 100 for value in values):
            return _direction(values[0], values[1])
        return None
    old_hits, new_hits = before.get("line_hits"), after.get("line_hits")
    if not isinstance(old_hits, dict) or not isinstance(new_hits, dict) or not old_hits or old_hits.keys() != new_hits.keys():
        return None
    if before.get("branch_hits", []) != after.get("branch_hits", []):
        return None
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in [*old_hits.values(), *new_hits.values()]):
        return None
    changes = [_direction(int(old_hits[key] > 0), int(new_hits[key] > 0)) for key in old_hits]
    if ComparisonResult.REGRESSION in changes:
        return ComparisonResult.REGRESSION
    if ComparisonResult.IMPROVEMENT in changes:
        return ComparisonResult.IMPROVEMENT
    return ComparisonResult.NO_CHANGE


def _classify(kind: str, before: dict[str, Any], after: dict[str, Any]) -> tuple[ComparisonResult, str]:
    if before == after:
        return ComparisonResult.NO_CHANGE, "same_content"
    old_data, new_data = _payload(before), _payload(after)
    if kind == "static_finding":
        ranks = {"note": 3, "warning": 2, "error": 1, "critical": 0}
        old_value, new_value = ranks.get(str(old_data.get("severity"))), ranks.get(str(new_data.get("severity")))
    else:
        old_value, new_value = _status_value(kind, old_data), _status_value(kind, new_data)
    if old_value is not None and new_value is not None:
        return _direction(old_value, new_value), "outcome_comparison"
    if kind == "coverage_slice":
        result = _coverage(old_data, new_data)
        if result is not None:
            return result, "coverage_comparison"
    return ComparisonResult.INCOMPARABLE, "changed_content_without_comparable_metric"


def _addition(kind: str, node: dict[str, Any]) -> ComparisonResult:
    if kind == "static_finding":
        return ComparisonResult.REGRESSION
    if kind == "coverage_slice":
        data = _payload(node)
        if _coverage(data, data) is None:
            return ComparisonResult.INCOMPARABLE
        return ComparisonResult.IMPROVEMENT  # 比較数値の上昇ではなく、検証可能な証跡の追加。
    score = _status_value(kind, _payload(node))
    if score is None:
        return ComparisonResult.INCOMPARABLE
    return ComparisonResult.IMPROVEMENT if score > 0 else ComparisonResult.REGRESSION


def compare_manifest_artifacts(root: Path, current: StoreManifest, baseline: StoreManifest) -> ComparisonStats:
    try:
        current_records, baseline_records = _records(root, current), _records(root, baseline)
    except (LocalStoreError, OSError, ValueError) as exc:
        return failed_comparison([{"issue": "artifact_comparison_unreadable", "error": str(exc), "severity": "hard_dq"}])
    diffs: list[ArtifactDiff] = []
    paired = added = removed = 0
    for key in sorted(current_records.keys() | baseline_records.keys()):
        new_record, old_record = current_records.get(key), baseline_records.get(key)
        details: dict[str, Any] = {"kind": key[0], "identity": key[1]}
        if old_record is None and new_record is not None:
            added += 1
            current_id, node = new_record
            result, reason = _addition(key[0], node), "new_artifact"
            baseline_id = None
        elif new_record is None and old_record is not None:
            removed += 1
            baseline_id, _ = old_record
            current_id = None
            result = ComparisonResult.INCOMPARABLE if key[0] == "static_finding" else ComparisonResult.REGRESSION
            reason = "removed_artifact"
        else:
            assert new_record is not None and old_record is not None
            paired += 1
            current_id, new_node = new_record
            baseline_id, old_node = old_record
            result, reason = _classify(key[0], old_node, new_node)
        details.update(reason=reason, current_artifact_id=current_id, baseline_artifact_id=baseline_id)
        diffs.append(ArtifactDiff(
            current_id or baseline_id or "", baseline.content_hashes.get(baseline_id or ""),
            current.content_hashes.get(current_id or ""), result, details,
        ))
    return (
        sum(item.result == ComparisonResult.IMPROVEMENT for item in diffs),
        sum(item.result == ComparisonResult.REGRESSION for item in diffs),
        sum(item.result == ComparisonResult.NO_CHANGE for item in diffs),
        paired, added, removed, diffs, [],
    )
