from __future__ import annotations

import json

import pytest

from hate.schema_resources import read_schema, validate_schema_instance
from hate.store import LocalStore, LocalStoreError
from hate.store.atomic_write import AtomicWriteError, complete_manifest_write
from hate.store.compare import compare_bundle_to_baseline, compare_bundles_direct
from hate.store.doctor import diagnose_run
from hate.store.indexes import build_indexes_for_bundle
from hate.store.replay import build_store_replay_report, replay_bundle


@pytest.fixture
def saved(tmp_path):
    store = LocalStore(tmp_path / "store")
    hold = dict(status="none", reason="test", held_since="2026-09-10T00:00:00Z", authorized_by="test")
    sources, results = {}, {}
    for run, status in (("baseline", "failed"), ("current", "passed")):
        source = tmp_path / f"{run}.json"
        source.write_text(json.dumps({"nodes": [{"kind": "test", "id": "one", "status": status}]}), encoding="utf-8")
        result = store.import_bundle(source, run, run, hold)
        assert result.success
        sources[run], results[run] = source, result
    return store, sources, hold, results


def _versions(result, changes):
    data = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    data["schema_versions"].update(changes)
    result.manifest_path.write_text(json.dumps(data), encoding="utf-8")
    return data


def _files(store):
    return {
        path.relative_to(store.store_root): path.read_bytes()
        for path in store.store_root.rglob("*")
        if path.is_file() and path != store.store_root / "locks" / "store.lock"
    }


CHANGES = [
    {"core": "HATE/v2", "bundle": "HATE/v1"},
    {"core": "HATE/v0.8", "bundle": "HATE/v1"},
    {"store": "2.0.0"}, {"store": "1.0.1"},
    {"bundle": "HATE/v2"}, {"bundle": "HATE/v0.8"},
    {"core": " ", "bundle": "HATE/v1"}, {"store": ""},
]
COMPONENT_CHANGES = [CHANGES[0], CHANGES[2], CHANGES[4]]


@pytest.mark.parametrize("changes", CHANGES)
def test_replay_and_doctor_check_each_manifest_version_without_masking(saved, changes):
    store, _, _, results = saved
    current = results["current"]
    _versions(current, changes)
    before = _files(store)
    expected = {key for key, value in changes.items() if value != "HATE/v1"}
    replay = replay_bundle(store, current.bundle_id)
    assert not replay.schema_compatible and replay.migration_hold
    assert replay.artifacts_replayed == 0 and replay.integrity_ok
    assert {item["component"] for item in replay.diagnostics if item.get("issue") == "store_schema_version_unsupported"} == expected
    doctor = diagnose_run(store, "current")
    assert doctor.hard_dq_count == 0
    assert {item.diagnostics["component"] for item in doctor.findings if item.category == "schema"} == expected
    report = build_store_replay_report(replay, doctor_report=doctor)
    assert report["readiness_effect"] == "hold"
    assert not validate_schema_instance(report, read_schema("store-replay-report.schema.json"))
    assert _files(store) == before


@pytest.mark.parametrize("changes", COMPONENT_CHANGES)
@pytest.mark.parametrize("reference_kind", ["run", "bundle"])
def test_unsupported_baseline_causes_migration_hold_with_valid_physical_reference(saved, changes, reference_kind):
    store, _, _, results = saved
    _versions(results["baseline"], changes)
    reference = "run:baseline" if reference_kind == "run" else "bundle:" + results["baseline"].bundle_id
    before = _files(store)
    replay = replay_bundle(store, results["current"].bundle_id, baseline_ref=reference)
    assert replay.baseline_valid and replay.integrity_ok
    assert not replay.schema_compatible and replay.migration_hold and replay.artifacts_replayed == 0
    assert any(item.get("issue") == "baseline_store_schema_version_unsupported" for item in replay.diagnostics)
    report = build_store_replay_report(replay)
    assert report["readiness_effect"] == "hold"
    assert report["baseline_resolution"]["baseline_bundle_id"] == results["baseline"].bundle_id
    assert not validate_schema_instance(report, read_schema("store-replay-report.schema.json"))
    assert _files(store) == before


@pytest.mark.parametrize("changes", COMPONENT_CHANGES)
@pytest.mark.parametrize("side", ["current", "baseline"])
def test_comparison_checks_versions_on_both_sides(saved, changes, side):
    store, _, _, results = saved
    _versions(results[side], changes)
    before = _files(store)
    reports = [
        compare_bundles_direct(store, results["current"].bundle_id, results["baseline"].bundle_id),
        compare_bundle_to_baseline(store, results["current"].bundle_id, baseline_ref="run:baseline"),
    ]
    for report in reports:
        assert report.comparison_result.value == "incomparable" and report.artifacts_compared == 0
        assert any(item.get("side") == side and item.get("component") in changes for item in report.diagnostics)
        assert all(item.get("severity") != "hard_dq" for item in report.diagnostics)
    assert _files(store) == before


@pytest.mark.parametrize("changes", COMPONENT_CHANGES)
@pytest.mark.parametrize("operation", ["read-run", "read-bundle", "reimport", "indexes", "complete", "hold"])
def test_current_format_operations_reject_unsupported_saved_versions_before_changes(saved, changes, operation):
    store, sources, hold, results = saved
    current = results["current"]
    manifest = _versions(current, changes)
    assert store.read_manifest("current").schema_versions == manifest["schema_versions"]
    before = _files(store)
    with pytest.raises((LocalStoreError, AtomicWriteError)) as caught:
        if operation == "read-run":
            store.read_bundle_by_run("current")
        elif operation == "read-bundle":
            store.read_bundle(current.bundle_id)
        elif operation == "reimport":
            store.import_bundle(sources["current"], "current", "current", hold)
        elif operation == "indexes":
            build_indexes_for_bundle(store.store_root, current.manifest_path.parent, manifest)
        elif operation == "hold":
            store.update_legal_hold("current", "active", "review", "test")
        else:
            complete_manifest_write(current.manifest_path, manifest, store.store_root, [])
    assert any(item.get("issue") == "store_schema_version_unsupported" for item in caught.value.diagnostics)
    assert _files(store) == before


def test_unrelated_component_versions_are_preserved_without_claiming_support_for_them(saved):
    store, sources, hold, results = saved
    current = results["current"]
    manifest = _versions(current, {"bundle": "HATE/v1", "adapter": "adapter/v99", "parser": "external"})
    replay = replay_bundle(store, current.bundle_id, baseline_ref="run:baseline")
    assert replay.schema_compatible and not replay.migration_hold and replay.artifacts_replayed == 1
    assert diagnose_run(store, "current").findings == []
    assert store.read_bundle_by_run("current") == json.loads(sources["current"].read_text(encoding="utf-8"))
    assert store.import_bundle(sources["current"], "current", "current", hold).success
    complete_manifest_write(current.manifest_path, manifest, store.store_root, [])
    build_indexes_for_bundle(store.store_root, current.manifest_path.parent, manifest)
    assert store.read_manifest("current").schema_versions == manifest["schema_versions"]


def test_real_baseline_corruption_remains_hard_dq_alongside_unsupported_version(saved):
    store, _, _, results = saved
    baseline = results["baseline"]
    manifest = _versions(baseline, {"store": "2.0.0"})
    (baseline.manifest_path.parent / f"{manifest['artifact_ids'][0]}.json").unlink()
    replay = replay_bundle(store, results["current"].bundle_id, baseline_ref="run:baseline")
    assert not replay.baseline_valid
    assert build_store_replay_report(replay)["readiness_effect"] == "hard_dq"


def test_latest_unsupported_baseline_is_reported_without_falling_back_to_older_copy(saved):
    store, sources, hold, results = saved
    sources["baseline"].write_text('{"nodes": [{"kind": "test", "id": "one", "status": "skipped"}]}', encoding="utf-8")
    latest = store.import_bundle(sources["baseline"], "baseline", "later", hold)
    assert latest.success
    _versions(latest, {"store": "2.0.0"})
    replay = replay_bundle(store, results["current"].bundle_id, baseline_ref="run:baseline")
    assert replay.migration_hold
    assert replay.baseline_resolution["baseline_bundle_id"] == latest.bundle_id
