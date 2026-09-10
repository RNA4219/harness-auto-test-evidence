from __future__ import annotations

import json

from hate.store import LocalStore
from hate.store.compare import ComparisonResult, compare_bundle_to_baseline
from hate.store.doctor import diagnose_full_store, diagnose_run
from hate.store.replay import replay_bundle, select_baseline_by_timestamp


def _shared_bundle(tmp_path):
    source = tmp_path / "source.json"
    source.write_text(json.dumps({"nodes": [{"id": "test-1", "kind": "test_result"}]}), encoding="utf-8")
    store = LocalStore(tmp_path / "store")
    hold = dict(status="none", reason="test", held_since="2026-09-10T00:00:00Z", authorized_by="test")
    first = store.import_bundle(source, "run-first", "revision-first", hold)
    second = store.import_bundle(source, "run-second", "revision-second", hold)
    assert first.success and second.success and first.bundle_id == second.bundle_id
    return store, first, second


def test_same_bundle_remains_in_both_run_histories(tmp_path):
    store, first, second = _shared_bundle(tmp_path)
    for run in ("run-first", "run-second"):
        assert store.list_bundles_for_run(run) == [first.bundle_id]
        manifest = store.read_manifest_by_bundle(first.bundle_id, run_id=run)
        assert manifest.run_id == run
        assert manifest.source_version == f"revision-{run.split('-')[1]}"
    assert store.list_bundles() == [second.bundle_id]


def test_baseline_selection_uses_requested_runs_manifest(tmp_path):
    store, first, _ = _shared_bundle(tmp_path)
    baseline = select_baseline_by_timestamp(store, "run-first")
    assert baseline is not None
    assert baseline.baseline_run_id == "run-first"
    assert baseline.baseline_bundle_id == first.bundle_id


def test_same_content_in_previous_run_is_a_valid_comparison_baseline(tmp_path):
    store, first, _ = _shared_bundle(tmp_path)
    report = compare_bundle_to_baseline(store, first.bundle_id, baseline_ref="run:run-first")
    assert report.comparison_result == ComparisonResult.NO_CHANGE
    assert report.baseline_bundle_id == first.bundle_id


def test_run_diagnosis_checks_that_runs_artifact_copy(tmp_path):
    store, first, _ = _shared_bundle(tmp_path)
    manifest = store.read_manifest("run-first")
    (first.manifest_path.parent / f"{manifest.artifact_ids[0]}.json").unlink()
    report = diagnose_run(store, "run-first")
    assert any(finding.category == "artifact" for finding in report.findings)
    other = diagnose_run(store, "run-second")
    assert not any(finding.category == "artifact" for finding in other.findings)
    assert any(finding.category == "artifact" for finding in diagnose_full_store(store).findings)


def test_replay_uses_bundle_id_and_requested_run_paths(tmp_path):
    store, first, _ = _shared_bundle(tmp_path)
    report = replay_bundle(store, first.bundle_id, run_id="run-first")
    assert report.run_id == "run-first"
    assert report.artifacts_replayed == 1
    assert report.artifacts_missing == 0
    assert report.hash_mismatches == 0
    assert report.schema_compatible
    assert not report.migration_hold


def test_replay_rejects_missing_hash_without_claiming_artifact_replayed(tmp_path):
    store, first, _ = _shared_bundle(tmp_path)
    data = json.loads(first.manifest_path.read_text(encoding="utf-8"))
    data["content_hashes"] = {}
    first.manifest_path.write_text(json.dumps(data), encoding="utf-8")
    report = replay_bundle(store, first.bundle_id, run_id="run-first")
    assert report.artifacts_replayed == 0
    assert report.hash_mismatches == 1
