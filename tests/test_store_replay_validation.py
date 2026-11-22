from __future__ import annotations

import json

import pytest

from hate.schema_resources import read_schema, validate_schema_instance
from hate.store import LocalStore
from hate.store.doctor import diagnose_full_store
from hate.store.indexes import HardDQFinding
from hate.store.replay import build_store_replay_report, replay_bundle, select_baseline_by_timestamp


@pytest.fixture
def imported(tmp_path):
    source = tmp_path / "source.json"
    source.write_text('{"nodes": [{"kind": "test_result", "status": "pass"}]}', encoding="utf-8")
    store = LocalStore(tmp_path / "store")
    hold = dict(status="none", reason="test", held_since="2026-09-10T00:00:00Z", authorized_by="test")
    first = store.import_bundle(source, "run-first", "revision-1", hold)
    source.write_text('{"nodes": [{"kind": "test_result", "status": "failed"}]}', encoding="utf-8")
    current = store.import_bundle(source, "run-current", "revision-2", hold)
    assert first.success and current.success
    return store, source, hold, first, current


def snapshot(store):
    return {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in store.store_root.rglob("*") if path.is_file()}


@pytest.mark.parametrize("change", ["missing_bundle", "bad_json", "modified_bundle", "erased_artifacts", "missing_artifact", "bad_artifact"])
def test_replay_corruption_cannot_produce_passing_envelope(imported, change):
    store, _, _, _, current = imported
    bundle_path = current.manifest_path.parent / "qeg-bundle.json"
    data = json.loads(current.manifest_path.read_text(encoding="utf-8"))
    if change == "missing_bundle":
        bundle_path.unlink()
    elif change == "bad_json":
        bundle_path.write_text("{broken", encoding="utf-8")
    elif change == "modified_bundle":
        bundle_path.write_text('{"nodes": []}', encoding="utf-8")
    elif change == "erased_artifacts":
        data["artifact_ids"] = []
        data["content_hashes"] = {}
        current.manifest_path.write_text(json.dumps(data), encoding="utf-8")
    else:
        path = current.manifest_path.parent / f"{data['artifact_ids'][0]}.json"
        if change == "missing_artifact":
            path.unlink()
        else:
            path.write_text("{}", encoding="utf-8")
    before = snapshot(store)
    replay = replay_bundle(store, current.bundle_id, run_id="run-current")
    assert not replay.integrity_ok
    assert replay.artifacts_replayed == 0
    assert any(item["severity"] == "hard_dq" for item in replay.diagnostics)
    report = build_store_replay_report(replay)
    assert report["readiness_effect"] == "hard_dq"
    assert not validate_schema_instance(report, read_schema("store-replay-report.schema.json"))
    assert snapshot(store) == before


@pytest.mark.parametrize("baseline", ["bundle:missing", "run:missing", "bundle:", "run:", "filename:any", "sort:any", "untyped", ""])
def test_invalid_baseline_is_resolved_and_reported(imported, baseline):
    store, _, _, _, current = imported
    before = snapshot(store)
    replay = replay_bundle(store, current.bundle_id, baseline_ref=baseline)
    assert replay.integrity_ok
    assert not replay.baseline_valid
    report = build_store_replay_report(replay)
    assert report["baseline_resolution"]["valid"] is False
    assert report["readiness_effect"] == "hard_dq"
    assert snapshot(store) == before


@pytest.mark.parametrize("by_run", [True, False])
def test_valid_baseline_resolution_survives_report_serialization(imported, by_run):
    store, _, _, first, current = imported
    reference = "run:run-first" if by_run else "bundle:" + first.bundle_id
    replay = replay_bundle(store, current.bundle_id, baseline_ref=reference)
    report = build_store_replay_report(replay.to_dict())
    assert report["readiness_effect"] == "pass"
    assert report["baseline_resolution"]["baseline_bundle_id"] == first.bundle_id
    assert report["baseline_resolution"]["baseline_run_id"] == "run-first"
    assert report["baseline_resolution"]["valid"]


@pytest.mark.parametrize("change", ["incomplete", "missing_artifact", "missing_bundle"])
def test_corrupt_explicit_baseline_cannot_pass(imported, change):
    store, _, _, first, current = imported
    data = json.loads(first.manifest_path.read_text(encoding="utf-8"))
    if change == "incomplete":
        data["completed"] = False
        data["import_status"]["phase"] = "importing"
        first.manifest_path.write_text(json.dumps(data), encoding="utf-8")
    elif change == "missing_bundle":
        (first.manifest_path.parent / "qeg-bundle.json").unlink()
    else:
        (first.manifest_path.parent / f"{data['artifact_ids'][0]}.json").unlink()
    replay = replay_bundle(store, current.bundle_id, baseline_ref="bundle:" + first.bundle_id)
    assert not replay.baseline_valid
    assert build_store_replay_report(replay)["readiness_effect"] == "hard_dq"


def test_timestamp_selection_compares_instants_instead_of_timestamp_strings(imported):
    store, source, hold, first, _ = imported
    second = store.import_bundle(source, "run-first", "revision-3", hold)
    for result, timestamp in ((first, "2026-09-10T10:00:00+09:00"), (second, "2026-09-10T02:00:00Z")):
        data = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        data["created_at"] = timestamp
        result.manifest_path.write_text(json.dumps(data), encoding="utf-8")
    selected = select_baseline_by_timestamp(store, "run-first")
    assert selected.baseline_bundle_id == second.bundle_id


def test_duplicate_bundle_index_blocks_default_resolution_and_is_diagnosed(imported):
    store, _, _, _, current = imported
    index = store.index_manager.bundles_index.index_path
    index.write_bytes(index.read_bytes() * 2)
    before = snapshot(store)
    with pytest.raises(HardDQFinding) as error:
        replay_bundle(store, current.bundle_id)
    assert error.value.missing_path == str(index)
    assert not diagnose_full_store(store).healthy
    assert snapshot(store) == before
    # 明示runの再生は保存コピーのみを使い、別コピーのaliasへ依存しない。
    assert replay_bundle(store, current.bundle_id, run_id="run-current").integrity_ok


def test_unsupported_schema_does_not_count_artifacts_as_replayed(imported):
    store, _, _, _, current = imported
    data = json.loads(current.manifest_path.read_text(encoding="utf-8"))
    data["schema_versions"]["bundle"] = "HATE/v0.8"
    current.manifest_path.write_text(json.dumps(data), encoding="utf-8")
    replay = replay_bundle(store, current.bundle_id)
    assert replay.migration_hold and replay.integrity_ok
    assert replay.artifacts_replayed == 0
    assert build_store_replay_report(replay)["readiness_effect"] == "hold"
