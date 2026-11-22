from __future__ import annotations

import copy
import json

import pytest

from hate.schema_resources import read_schema, validate_schema_instance
from hate.store import LocalStore, LocalStoreError, StoreManifest
from hate.store import atomic_write as writer
from hate.store.doctor import diagnose_run
from hate.store.replay import replay_bundle


@pytest.fixture
def saved(tmp_path):
    source = tmp_path / "source.json"
    source.write_text('{"nodes": [{"kind": "test", "id": "one", "status": "passed"}]}', encoding="utf-8")
    store = LocalStore(tmp_path / "store")
    hold = dict(status="none", reason="test", held_since="2026-09-10T00:00:00Z", authorized_by="test")
    result = store.import_bundle(source, "run-1", "revision-1", hold)
    assert result.success
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    return store, source, hold, result, manifest


def _files(root):
    return {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*") if path.is_file() and path != root / "locks" / "store.lock"
    }


@pytest.mark.parametrize("completed,phase", [
    (True, "pending"), (True, "importing"), (True, "failed"), (True, "quarantined"), (False, "completed"),
])
def test_completion_flag_and_declared_phase_must_agree(saved, completed, phase):
    store, _, _, result, manifest = saved
    manifest["completed"] = completed
    manifest["import_status"]["phase"] = phase
    result.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    before = _files(store.store_root)
    assert validate_schema_instance(manifest, read_schema("store-manifest.schema.json"))
    with pytest.raises(LocalStoreError):
        StoreManifest.from_dict(manifest)
    assert not writer.is_complete_manifest(result.manifest_path)
    with pytest.raises(LocalStoreError):
        store.read_bundle_by_run("run-1")
    assert not diagnose_run(store, "run-1").healthy
    assert _files(store.store_root) == before


@pytest.mark.parametrize("completed,phase", [
    (True, "completed"), (False, "pending"), (False, "importing"), (False, "failed"), (False, "quarantined"),
    (True, None), (False, None),
])
def test_consistent_and_legacy_manifest_states_remain_readable(saved, completed, phase):
    store, _, _, result, manifest = saved
    manifest["completed"] = completed
    if phase is None:
        manifest.pop("import_status")
    else:
        manifest["import_status"]["phase"] = phase
    result.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert not validate_schema_instance(manifest, read_schema("store-manifest.schema.json"))
    assert store.read_manifest("run-1").completed is completed
    assert writer.is_complete_manifest(result.manifest_path) is completed


@pytest.mark.parametrize("damage", [
    "missing-bundle", "missing-artifact", "missing-hash", "erased-inventory", "changed-bundle",
    "bad-artifact", "invalid-bundle", "wrong-filename", "missing-extra", "directory-extra",
])
def test_completion_checks_required_physical_files_even_when_caller_list_omits_them(saved, damage):
    store, _, _, result, manifest = saved
    directory = result.manifest_path.parent
    bundle = directory / "qeg-bundle.json"
    artifact = directory / f"{manifest['artifact_ids'][0]}.json"
    target = result.manifest_path
    supplied_files = []
    if damage == "missing-bundle":
        bundle.unlink()
    elif damage == "missing-artifact":
        artifact.unlink()
    elif damage == "missing-hash":
        manifest["content_hashes"] = {}
    elif damage == "erased-inventory":
        manifest["artifact_ids"], manifest["content_hashes"] = [], {}
    elif damage == "changed-bundle":
        bundle.write_text('{"nodes": []}', encoding="utf-8")
    elif damage == "bad-artifact":
        artifact.write_bytes(b"{}")
    elif damage == "invalid-bundle":
        bundle.write_text('{"nodes": "invalid"}', encoding="utf-8")
    elif damage == "wrong-filename":
        target = directory / "wrong-name.json"
    elif damage == "missing-extra":
        supplied_files = [directory / "missing.log"]
    else:
        supplied_files = [directory]
    manifest["completed"] = False
    manifest["import_status"]["phase"] = "importing"
    before = _files(store.store_root)
    input_before = copy.deepcopy(manifest)
    with pytest.raises(writer.AtomicWriteError):
        writer.complete_manifest_write(target, manifest, store.store_root, supplied_files)
    assert manifest == input_before
    assert _files(store.store_root) == before


def test_successful_completion_preserves_diagnostics_and_updates_callers_mapping(saved):
    store, _, _, result, manifest = saved
    manifest["completed"] = False
    manifest["import_status"] = {"phase": "importing", "diagnostics": [{"info": "source verified"}], "attempt": 2}
    original_status = copy.deepcopy(manifest["import_status"])
    completed = writer.complete_manifest_write(result.manifest_path, manifest, store.store_root, [])
    assert completed is manifest
    assert completed["completed"] is True
    assert completed["import_status"] == {**original_status, "phase": "completed"}
    assert completed == json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert store.verify_integrity("run-1")["integrity_ok"]


@pytest.mark.parametrize("failure", [OSError, KeyboardInterrupt])
def test_completion_failure_does_not_mark_callers_input_complete(saved, monkeypatch, failure):
    store, _, _, result, manifest = saved
    manifest["completed"] = False
    manifest["import_status"]["phase"] = "importing"
    input_before, files_before = copy.deepcopy(manifest), _files(store.store_root)

    def failed_replace(*args):
        raise failure("manifest publication interrupted")

    monkeypatch.setattr(writer.os, "replace", failed_replace)
    with pytest.raises(writer.AtomicWriteError if failure is OSError else KeyboardInterrupt):
        writer.complete_manifest_write(result.manifest_path, manifest, store.store_root, [])
    assert manifest == input_before
    assert _files(store.store_root) == files_before


def test_completion_sync_uncertainty_reports_published_state_without_success_mutation(saved, monkeypatch):
    store, _, _, result, manifest = saved
    manifest["completed"] = False
    manifest["import_status"]["phase"] = "importing"
    before = copy.deepcopy(manifest)

    def failed_sync(parent):
        raise OSError("directory sync interrupted")

    monkeypatch.setattr(writer, "_sync_parent_directory", failed_sync)
    with pytest.raises(writer.AtomicWriteError) as caught:
        writer.complete_manifest_write(result.manifest_path, manifest, store.store_root, [])
    assert caught.value.diagnostics[0]["published"] is True
    assert manifest == before
    assert writer.is_complete_manifest(result.manifest_path)


def test_uppercase_manifest_hashes_match_actual_digest_through_completion_and_replay(saved):
    store, _, _, result, manifest = saved
    manifest["content_hashes"] = {key: "sha256:" + value[7:].upper() for key, value in manifest["content_hashes"].items()}
    files = [result.manifest_path.parent / "qeg-bundle.json"]
    files.extend(result.manifest_path.parent / f"{key}.json" for key in manifest["artifact_ids"])
    writer.complete_manifest_write(result.manifest_path, manifest, store.store_root, files)
    saved_bytes = _files(store.store_root)
    assert store.verify_integrity("run-1")["integrity_ok"]
    report = replay_bundle(store, result.bundle_id)
    assert report.integrity_ok and report.artifacts_replayed == 1
    assert diagnose_run(store, "run-1").healthy
    assert _files(store.store_root) == saved_bytes


def test_import_detects_missing_written_artifact_before_commit_and_restores_indexes(saved, monkeypatch):
    from hate.store import local_store

    store, source, hold, _, _ = saved
    source.write_text('{"nodes": [{"kind": "test", "id": "two", "status": "failed"}]}', encoding="utf-8")
    before = {path: content for path, content in _files(store.store_root).items() if path.parts[0] in {"runs", "indexes"}}
    original_complete = local_store.complete_manifest_write

    def lost_artifact_before_completion(**kwargs):
        artifact = kwargs["manifest_path"].parent / f"{kwargs['manifest_content']['artifact_ids'][0]}.json"
        artifact.unlink()
        kwargs["bundle_files"] = [path for path in kwargs["bundle_files"] if path != artifact]
        return original_complete(**kwargs)

    monkeypatch.setattr(local_store, "complete_manifest_write", lost_artifact_before_completion)
    result = store.import_bundle(source, "run-2", "revision-2", hold)
    assert not result.success
    assert store.list_runs() == ["run-1"]
    after = {path: content for path, content in _files(store.store_root).items() if path.parts[0] in {"runs", "indexes"}}
    assert after == before
    assert store.verify_integrity("run-1")["integrity_ok"]


@pytest.mark.parametrize("changed_during_validation", [False, True])
def test_direct_completion_rechecks_store_version_before_publication(saved, monkeypatch, changed_during_validation):
    from hate.store import completion

    store, _, _, result, manifest = saved
    marker = store.store_root / "store-version.json"
    original_verify = completion.verify_bundle_copy
    expected = None

    def change_version():
        nonlocal expected
        version = json.loads(marker.read_text(encoding="utf-8"))
        version["store_version"] = "2.0.0"
        marker.write_text(json.dumps(version), encoding="utf-8")
        expected = _files(store.store_root)

    def verify_then_change(*args):
        diagnostics = original_verify(*args)
        change_version()
        return diagnostics

    if changed_during_validation:
        monkeypatch.setattr(completion, "verify_bundle_copy", verify_then_change)
    else:
        change_version()
    before = copy.deepcopy(manifest)
    with pytest.raises(LocalStoreError):
        writer.complete_manifest_write(result.manifest_path, manifest, store.store_root, [])
    assert manifest == before
    assert _files(store.store_root) == expected
