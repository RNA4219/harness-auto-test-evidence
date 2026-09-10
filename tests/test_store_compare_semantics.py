from __future__ import annotations

import json

import pytest

from hate.store import LocalStore
from hate.store.compare import compare_bundle_to_baseline, compare_bundles_direct
from hate.store.replay import build_store_replay_report, replay_bundle


def _pair(tmp_path, before, after):
    store = LocalStore(tmp_path / "store")
    hold = dict(status="none", reason="test", held_since="2026-09-10T00:00:00Z", authorized_by="test")
    results = []
    for run, nodes in (("baseline", before), ("current", after)):
        source = tmp_path / f"{run}.json"
        source.write_text(json.dumps({"nodes": nodes}), encoding="utf-8")
        result = store.import_bundle(source, run, run, hold)
        assert result.success
        results.append(result)
    return store, results[0], results[1]


@pytest.mark.parametrize("kind,field,before,after,expected", [
    ("test_result", "outcome", "failed", "passed", "improvement"),
    ("test", "status", "passed", "failed", "regression"),
    ("test", "status", "passed", "skipped", "incomparable"),
    ("contract_evidence", "status", "failed", "passed", "improvement"),
    ("mutation_evidence", "status", "survived", "killed", "improvement"),
    ("mutation_evidence", "status", "killed", "survived", "regression"),
    ("static_finding", "severity", "critical", "warning", "improvement"),
    ("coverage_slice", "coverage_percent", 30, 80, "improvement"),
    ("coverage_slice", "coverage_percent", 80, 30, "regression"),
])
def test_semantic_outcomes_match_the_same_item_across_content_hash_changes(tmp_path, kind, field, before, after, expected):
    old_node = {"id": "stable-item", "kind": kind, "data": {field: before}}
    new_node = {"id": "stable-item", "kind": kind, "data": {field: after}}
    store, baseline, current = _pair(tmp_path, [old_node], [new_node])
    report = compare_bundles_direct(store, current.bundle_id, baseline.bundle_id)
    assert report.comparison_result.value == expected
    assert report.artifacts_compared == 1
    assert report.artifacts_missing_in_baseline == report.artifacts_missing_in_current == 0
    diff = report.artifact_diffs[0]
    assert diff.details["baseline_artifact_id"] != diff.details["current_artifact_id"]
    assert diff.baseline_hash != diff.current_hash


@pytest.mark.parametrize("after,expected", [({"1": 1, "2": 3}, "improvement"), ({"1": 0, "2": 1}, "regression"), ({"1": 4, "2": 0}, "no_change"), ({"1": 1}, "incomparable")])
def test_coverage_compares_executed_lines_and_preserves_scope_uncertainty(tmp_path, after, expected):
    before = {"id": "coverage:app", "kind": "coverage", "data": {"line_hits": {"1": 1, "2": 0}}}
    current_node = {"id": "coverage:app", "kind": "coverage", "data": {"line_hits": after}}
    store, baseline, current = _pair(tmp_path, [before], [current_node])
    assert compare_bundles_direct(store, current.bundle_id, baseline.bundle_id).comparison_result.value == expected


def test_unknown_changed_content_is_not_called_no_change(tmp_path):
    before = {"id": "item", "kind": "mutation_evidence", "data": {"status": "ignored", "message": "old"}}
    after = {**before, "data": {"status": "ignored", "message": "new"}}
    store, baseline, current = _pair(tmp_path, [before], [after])
    comparison = compare_bundles_direct(store, current.bundle_id, baseline.bundle_id)
    assert comparison.comparison_result.value == "incomparable"
    assert build_store_replay_report(replay_bundle(store, current.bundle_id), comparison_report=comparison)["readiness_effect"] == "hold"


def test_new_coverage_without_a_known_metric_is_not_called_improvement(tmp_path):
    store, baseline, current = _pair(tmp_path, [], [{"id": "coverage:item", "kind": "coverage", "data": {"custom": "unknown"}}])
    report = compare_bundles_direct(store, current.bundle_id, baseline.bundle_id)
    assert report.comparison_result.value == "incomparable"
    assert report.improvements == 0


@pytest.mark.parametrize("side", ["current", "baseline"])
@pytest.mark.parametrize("change", ["missing_bundle", "artifact", "missing_hash", "erased_list"])
def test_corrupt_copy_never_reports_no_change(tmp_path, side, change):
    node = {"id": "item", "kind": "test_result", "status": "passed"}
    store, baseline, current = _pair(tmp_path, [node], [node])
    target = current if side == "current" else baseline
    data = json.loads(target.manifest_path.read_text(encoding="utf-8"))
    if change == "missing_bundle":
        (target.manifest_path.parent / "qeg-bundle.json").unlink()
    elif change == "artifact":
        (target.manifest_path.parent / f"{data['artifact_ids'][0]}.json").write_text("{}", encoding="utf-8")
    else:
        data["content_hashes"] = {}
        if change == "erased_list":
            data["artifact_ids"] = []
        target.manifest_path.write_text(json.dumps(data), encoding="utf-8")
    before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in store.store_root.rglob("*") if path.is_file()}
    report = compare_bundles_direct(store, current.bundle_id, baseline.bundle_id, run_id_a="current", run_id_b="baseline")
    assert report.comparison_result.value == "incomparable"
    assert report.artifacts_compared == 0
    assert any(item["severity"] == "hard_dq" and item["side"] == side for item in report.diagnostics)
    assert {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in before} == before


def test_duplicate_stable_identity_is_reported_as_ambiguous(tmp_path):
    nodes = [
        {"id": f"attempt-{number}", "kind": "test_result", "data": {"canonical_test_id": "same", "status": outcome}}
        for number, outcome in enumerate(("passed", "failed"))
    ]
    store, baseline, current = _pair(tmp_path, nodes[:1], nodes)
    report = compare_bundles_direct(store, current.bundle_id, baseline.bundle_id)
    assert report.comparison_result.value == "incomparable"
    assert any(item["severity"] == "hard_dq" for item in report.diagnostics)


def test_key_order_only_changes_do_not_become_artifact_additions(tmp_path):
    node = {"id": "item", "kind": "test_result", "status": "passed"}
    store, baseline, current = _pair(tmp_path, [node], [dict(reversed(list(node.items())))])
    report = compare_bundles_direct(store, current.bundle_id, baseline.bundle_id, run_id_a="current", run_id_b="baseline")
    assert report.comparison_result.value == "no_change"
    assert report.artifacts_compared == 1
    assert report.improvements == report.regressions == 0


def test_same_bundle_uses_explicit_run_metadata_in_baseline_comparison(tmp_path):
    node = {"id": "item", "kind": "test_result", "status": "passed"}
    store, baseline, current = _pair(tmp_path, [node], [node])
    report = compare_bundle_to_baseline(store, current.bundle_id, baseline_ref="run:baseline", run_id="current")
    assert report.run_id == "current" and report.baseline_run_id == "baseline"
    assert report.baseline_bundle_id == baseline.bundle_id
