from __future__ import annotations

import json
import shutil

import pytest

from hate.store import LocalStore, LocalStoreError
from hate.store.atomic_write import AtomicWriteError, compute_file_hash
from hate.store.indexes import HardDQFinding, StoreIndex, build_indexes_for_bundle


@pytest.fixture
def saved(tmp_path):
    source = tmp_path / "source.json"
    source.write_text(json.dumps({"nodes": [{"id": "test-1", "kind": "test", "data": {"status": "passed"}}]}), encoding="utf-8")
    store = LocalStore(tmp_path / "store")
    hold = dict(status="active", reason="keep", held_since="2026-09-10T00:00:00Z", authorized_by="test")
    result = store.import_bundle(source, "run-1", "revision-1", hold)
    assert result.success
    manifest = store.read_manifest("run-1").to_dict()
    return store, source, hold, result.manifest_path.parent, manifest


def _indexes(store):
    return {path.name: path.read_bytes() for path in (store.store_root / "indexes").glob("*.jsonl")}


def _bundle_bytes(store):
    return {path.relative_to(store.store_root): path.read_bytes() for path in (store.store_root / "runs").rglob("*.json")}


def _empty_indexes(store):
    for path in (store.store_root / "indexes").glob("*.jsonl"):
        path.write_bytes(b"")


def test_builder_restores_current_layout_without_changing_evidence(saved):
    store, _, _, directory, manifest = saved
    expected = _indexes(store)
    evidence = _bundle_bytes(store)
    _empty_indexes(store)
    hashes = build_indexes_for_bundle(store.store_root, directory, manifest)
    assert _indexes(store) == expected
    assert _bundle_bytes(store) == evidence
    assert store.verify_integrity("run-1")["integrity_ok"]
    assert hashes == {index.index_type: compute_file_hash(index.index_path) for index in store.index_manager._all_indexes()}


@pytest.mark.parametrize("damage", ["bundle-missing", "artifact-missing", "artifact-hash", "incomplete", "stale-manifest"])
def test_invalid_copy_or_manifest_is_rejected_before_index_changes(saved, damage):
    store, _, _, directory, manifest = saved
    artifact = directory / f"{manifest['artifact_ids'][0]}.json"
    if damage == "bundle-missing":
        (directory / "qeg-bundle.json").unlink()
    elif damage == "artifact-missing":
        artifact.unlink()
    elif damage == "artifact-hash":
        artifact.write_bytes(b"{}")
    elif damage == "incomplete":
        manifest["completed"] = False
        manifest["import_status"]["phase"] = "importing"
        (directory / "store-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    else:
        manifest["legal_hold"]["reason"] = "stale caller"
    before, evidence = _indexes(store), _bundle_bytes(store)
    with pytest.raises((LocalStoreError, HardDQFinding)):
        build_indexes_for_bundle(store.store_root, directory, manifest)
    assert _indexes(store) == before
    assert _bundle_bytes(store) == evidence
    assert not (store.store_root / "migrations" / "pending-import").exists()


@pytest.mark.parametrize("failure", ["write", "interrupt"])
def test_partial_index_update_restores_indexes_and_keeps_saved_bundle(saved, monkeypatch, failure):
    store, _, _, directory, manifest = saved
    _empty_indexes(store)
    before, evidence = _indexes(store), _bundle_bytes(store)
    save = StoreIndex.save

    def fail(index):
        if index.index_type == "artifacts":
            if failure == "interrupt":
                raise KeyboardInterrupt
            raise AtomicWriteError("simulated failure", index.index_path, "rename")
        return save(index)

    monkeypatch.setattr(StoreIndex, "save", fail)
    with pytest.raises(KeyboardInterrupt if failure == "interrupt" else AtomicWriteError):
        build_indexes_for_bundle(store.store_root, directory, manifest)
    assert _indexes(store) == before
    assert _bundle_bytes(store) == evidence
    assert not (store.store_root / "migrations" / "pending-import").exists()


def test_reindexing_history_does_not_rewind_existing_aliases(saved):
    store, source, hold, directory, manifest = saved
    assert store.import_bundle(source, "run-2", "revision-1", hold).success
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["revision"] = 2
    source.write_text(json.dumps(payload), encoding="utf-8")
    assert store.import_bundle(source, "run-1", "revision-2", hold).success
    before = _indexes(store)
    build_indexes_for_bundle(store.store_root, directory, manifest)
    assert _indexes(store) == before
    assert store.read_bundle_by_run("run-1") == payload


def test_missing_run_alias_uses_latest_completed_history(saved):
    store, source, hold, directory, manifest = saved
    payload = {"nodes": [], "revision": 2}
    source.write_text(json.dumps(payload), encoding="utf-8")
    newest = store.import_bundle(source, "run-1", "revision-2", hold)
    assert newest.success
    (store.store_root / "indexes" / "runs.jsonl").write_bytes(b"")
    build_indexes_for_bundle(store.store_root, directory, manifest)
    assert store.read_manifest("run-1").bundle_id == newest.bundle_id
    assert store.read_bundle_by_run("run-1") == payload


def test_builder_works_with_saved_files_without_initialized_store_infrastructure(saved, tmp_path):
    store, _, _, directory, manifest = saved
    target = tmp_path / "restored"
    shutil.copytree(store.store_root / "runs", target / "runs")
    copied_directory = target / directory.relative_to(store.store_root)
    hashes = build_indexes_for_bundle(target, copied_directory, manifest)
    assert len(hashes) == 7
    assert LocalStore(target).verify_integrity("run-1")["integrity_ok"]


@pytest.mark.parametrize("damage", ["hash", "metadata"])
def test_broken_existing_alias_is_not_silently_overwritten(saved, damage):
    store, _, _, directory, manifest = saved
    path = store.store_root / "indexes" / "artifacts.jsonl"
    entry = json.loads(path.read_text(encoding="utf-8"))
    if damage == "hash":
        entry["hash"] = "sha256:" + "0" * 64
    else:
        entry["metadata"]["run_id"] = "wrong-run"
    path.write_text(json.dumps(entry) + "\n", encoding="utf-8")
    before, evidence = _indexes(store), _bundle_bytes(store)
    with pytest.raises((LocalStoreError, HardDQFinding)):
        build_indexes_for_bundle(store.store_root, directory, manifest)
    assert _indexes(store) == before
    assert _bundle_bytes(store) == evidence


def test_missing_run_alias_uses_instants_and_rejects_ambiguous_history(saved):
    store, source, hold, directory, manifest = saved
    source.write_text('{"nodes": [], "revision": 2}', encoding="utf-8")
    newest = store.import_bundle(source, "run-1", "revision-2", hold)
    assert newest.success
    latest = json.loads(newest.manifest_path.read_text(encoding="utf-8"))
    manifest["created_at"] = "2026-09-10T08:00:00+09:00"
    latest["created_at"] = "2026-09-10T00:00:00Z"
    (directory / "store-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    newest.manifest_path.write_text(json.dumps(latest), encoding="utf-8")
    (store.store_root / "indexes" / "runs.jsonl").write_bytes(b"")
    build_indexes_for_bundle(store.store_root, directory, manifest)
    assert store.read_manifest("run-1").bundle_id == newest.bundle_id
    latest["created_at"] = "2026-09-09T23:00:00Z"
    newest.manifest_path.write_text(json.dumps(latest), encoding="utf-8")
    (store.store_root / "indexes" / "runs.jsonl").write_bytes(b"")
    before = _indexes(store)
    with pytest.raises(LocalStoreError, match="ambiguous"):
        build_indexes_for_bundle(store.store_root, directory, manifest)
    assert _indexes(store) == before


def test_failed_recovery_retains_index_backups_and_never_quarantines_complete_bundle(saved, monkeypatch):
    from hate.store import transaction

    store, _, _, directory, manifest = saved
    _empty_indexes(store)
    before, evidence = _indexes(store), _bundle_bytes(store)
    save, write = StoreIndex.save, transaction.atomic_write_bytes

    def fail_save(index):
        if index.index_type == "artifacts":
            raise AtomicWriteError("simulated write failure", index.index_path, "rename")
        return save(index)

    def fail_restore(target, content, root):
        if target.parent == root / "indexes":
            raise AtomicWriteError("simulated recovery failure", target, "rename")
        return write(target, content, root)

    monkeypatch.setattr(StoreIndex, "save", fail_save)
    monkeypatch.setattr(transaction, "atomic_write_bytes", fail_restore)
    with pytest.raises(LocalStoreError, match="recovery"):
        build_indexes_for_bundle(store.store_root, directory, manifest)
    pending = store.store_root / "migrations" / "pending-import"
    assert json.loads((pending / "journal.json").read_text(encoding="utf-8"))["version"] == 2
    assert not (pending / "failed-bundle").exists()
    assert _bundle_bytes(store) == evidence
    monkeypatch.setattr(transaction, "atomic_write_bytes", write)
    LocalStore(store.store_root)
    assert _indexes(store) == before
    assert _bundle_bytes(store) == evidence
    assert not pending.exists()


def test_commit_sync_uncertainty_keeps_completed_index_update(saved, monkeypatch):
    from hate.store import transaction

    store, _, _, directory, manifest = saved
    expected, evidence = _indexes(store), _bundle_bytes(store)
    _empty_indexes(store)
    write = transaction.atomic_write_json

    def uncertain_commit(path, content, root):
        result = write(path, content, root)
        if content.get("state") == "committed":
            raise AtomicWriteError("simulated commit sync failure", path, "fsync", [{"published": True}])
        return result

    monkeypatch.setattr(transaction, "atomic_write_json", uncertain_commit)
    with pytest.raises(LocalStoreError, match="durability uncertain"):
        build_indexes_for_bundle(store.store_root, directory, manifest)
    assert _indexes(store) == expected
    assert _bundle_bytes(store) == evidence
    LocalStore(store.store_root)
    assert not (store.store_root / "migrations" / "pending-import").exists()
