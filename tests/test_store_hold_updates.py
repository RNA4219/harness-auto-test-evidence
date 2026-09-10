from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import pytest

from hate.schema_resources import read_schema, validate_schema_instance
from hate.store import LocalStore, StoreManifest
from hate.store.atomic_write import AtomicWriteError
from hate.store.replay import replay_bundle


@pytest.fixture
def saved(tmp_path):
    source = tmp_path / "source.json"
    source.write_text('{"nodes": [{"kind": "test", "id": "one", "status": "passed"}]}', encoding="utf-8")
    store = LocalStore(tmp_path / "store")
    hold = dict(status="none", reason="test", held_since="2026-01-01T00:00:00Z", authorized_by="creator")
    result = store.import_bundle(source, "run-1", "revision-1", hold)
    assert result.success
    return store, source, hold, result


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path, data):
    assert not validate_schema_instance(data, read_schema("store-manifest.schema.json"))
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _files(root):
    return {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*") if path.is_file() and path != root / "locks" / "store.lock"
    }


@pytest.mark.parametrize("status", [None, {}, {"phase": "completed", "diagnostics": []}, {
    "phase": "completed", "diagnostics": [{"message": "取り込み時の確認", "sourceRefs": ["source:one"]}],
    "operation_id": "import-1",
}])
def test_manifest_roundtrip_preserves_optional_import_evidence(saved, status):
    _, _, _, result = saved
    data = _read(result.manifest_path)
    if status is None:
        data.pop("import_status")
    else:
        data["import_status"] = status
    assert StoreManifest.from_dict(data).to_dict() == data


def test_hold_update_preserves_import_evidence_and_other_manifest_fields(saved):
    store, _, _, result = saved
    path = result.manifest_path
    before = _read(path)
    before["import_status"]["diagnostics"] = [{"message": "original import evidence", "details": {"attempt": 2}}]
    _write(path, before)
    previous_files = _files(store.store_root)
    updated = store.update_legal_hold("run-1", "active", "review", "holder")
    after = _read(path)
    assert {key: value for key, value in after.items() if key != "legal_hold"} == {
        key: value for key, value in before.items() if key != "legal_hold"
    }
    assert updated.to_dict() == after
    current_files = _files(store.store_root)
    assert {key for key in previous_files.keys() | current_files.keys() if previous_files.get(key) != current_files.get(key)} == {
        path.relative_to(store.store_root)
    }
    assert LocalStore(store.store_root).verify_integrity("run-1")["integrity_ok"]


def test_replay_manifest_fingerprint_includes_saved_import_evidence(saved):
    store, _, _, result = saved
    before = replay_bundle(store, result.bundle_id, run_id="run-1")
    data = _read(result.manifest_path)
    data["import_status"]["diagnostics"] = [{"info": "verified after import"}]
    _write(result.manifest_path, data)
    report = replay_bundle(store, result.bundle_id, run_id="run-1")
    expected = "sha256:" + hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert report.source_bundle_hash == expected
    assert report.source_bundle_hash != before.source_bundle_hash
    assert report.replay_hash != before.replay_hash
    assert report.integrity_ok


@pytest.fixture
def frozen_clock(monkeypatch):
    from hate.store import local_store

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 9, 10, 12, tzinfo=UTC)

    monkeypatch.setattr(local_store, "datetime", Clock)
    return Clock.now().isoformat()


@pytest.mark.parametrize("previous_status", ["none", "pending", "released", "active"])
def test_activation_records_current_start_and_preserves_ongoing_start(saved, frozen_clock, previous_status):
    store, _, _, result = saved
    data = _read(result.manifest_path)
    data["legal_hold"]["status"] = previous_status
    if previous_status == "released":
        data["legal_hold"].update(released_at="2026-02-01T00:00:00Z", release_authorization={"authorized_by": "releaser"})
    _write(result.manifest_path, data)
    updated = store.update_legal_hold("run-1", "active", "review", "holder")
    expected = data["legal_hold"]["held_since"] if previous_status == "active" else frozen_clock
    assert updated.legal_hold["held_since"] == expected
    assert "released_at" not in updated.legal_hold and "release_authorization" not in updated.legal_hold
    assert _read(result.manifest_path)["legal_hold"] == updated.legal_hold


@pytest.mark.parametrize("previous_status", ["none", "pending", "active"])
def test_release_records_one_event_without_changing_activation_time(saved, frozen_clock, previous_status):
    store, _, _, result = saved
    data = _read(result.manifest_path)
    data["legal_hold"]["status"] = previous_status
    _write(result.manifest_path, data)
    updated = store.update_legal_hold("run-1", "released", "review finished", "releaser")
    assert updated.legal_hold["held_since"] == data["legal_hold"]["held_since"]
    assert updated.legal_hold["released_at"] == frozen_clock
    assert updated.legal_hold["release_authorization"] == {"authorized_by": "releaser"}


@pytest.mark.parametrize("release_evidence", [False, True])
def test_same_released_state_preserves_original_release_evidence(saved, frozen_clock, release_evidence):
    store, _, _, result = saved
    data = _read(result.manifest_path)
    hold = data["legal_hold"]
    hold["status"] = "released"
    if release_evidence:
        hold.update(released_at="2026-02-01T00:00:00Z", release_authorization={"authorized_by": "original", "ticket": "approval-1"})
    _write(result.manifest_path, data)
    updated = store.update_legal_hold("run-1", "released", "reason corrected", "editor")
    assert updated.legal_hold == {**hold, "reason": "reason corrected", "authorized_by": "editor"}


@pytest.mark.parametrize("mode", ["shared-bundle", "run-history"])
def test_hold_update_changes_only_requested_runs_current_manifest(saved, mode):
    store, source, hold, first = saved
    if mode == "run-history":
        source.write_text('{"nodes": [{"kind": "test", "id": "one", "status": "failed"}]}', encoding="utf-8")
    second = store.import_bundle(source, "run-1" if mode == "run-history" else "run-2", "revision-2", hold)
    assert second.success
    target = second if mode == "run-history" else first
    before = _files(store.store_root)
    store.update_legal_hold("run-1", "active", "review", "holder")
    after = _files(store.store_root)
    assert {key for key in before.keys() | after.keys() if before.get(key) != after.get(key)} == {
        target.manifest_path.relative_to(store.store_root)
    }
    assert store.verify_integrity("run-1")["integrity_ok"]


@pytest.mark.parametrize("failure", [OSError, KeyboardInterrupt])
def test_hold_update_replace_failure_preserves_all_existing_evidence(saved, monkeypatch, failure):
    from hate.store import atomic_write

    store, _, _, _ = saved
    before = _files(store.store_root)

    def fail_replace(*args):
        raise failure("hold update interrupted")

    monkeypatch.setattr(atomic_write.os, "replace", fail_replace)
    with pytest.raises(AtomicWriteError if failure is OSError else KeyboardInterrupt):
        store.update_legal_hold("run-1", "active", "review", "holder")
    assert _files(store.store_root) == before
