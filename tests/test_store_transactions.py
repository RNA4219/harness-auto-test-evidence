from __future__ import annotations

import json

import pytest

import hate.store.local_store as store_module
from hate.store import LocalStore, LocalStoreError
from hate.store.atomic_write import AtomicWriteError
from hate.store.indexes import StoreIndex


@pytest.fixture
def imported(tmp_path):
    source = tmp_path / "source.json"
    source.write_text(json.dumps({"nodes": [{"id": "test-1", "kind": "test_result"}]}), encoding="utf-8")
    hold = dict(status="none", reason="test", held_since="2026-09-10T00:00:00Z", authorized_by="test")
    store = LocalStore(tmp_path / "store")
    assert store.import_bundle(source, "original", "revision-1", hold).success
    return store, source, hold


def _indexes(store):
    return {path.name: path.read_bytes() for path in (store.store_root / "indexes").glob("*.jsonl")}


@pytest.mark.parametrize("failure", ["second-index", "manifest", "published-manifest", "interrupt"])
@pytest.mark.parametrize("existing_run", [False, True])
def test_failed_import_restores_indexes_and_previous_run(imported, monkeypatch, failure, existing_run):
    store, source, hold = imported
    before = _indexes(store)
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["revision"] = 2
    source.write_text(json.dumps(payload), encoding="utf-8")
    save = StoreIndex.save
    complete = store_module.complete_manifest_write

    def failed_save(index):
        if index.index_type == "bundles":
            raise AtomicWriteError("simulated index failure", index.index_path, "rename")
        return save(index)

    def failed_completion(**kwargs):
        if failure == "published-manifest":
            complete(**kwargs)
        if failure == "interrupt":
            raise KeyboardInterrupt
        raise AtomicWriteError("simulated manifest failure", kwargs["manifest_path"], "manifest")

    if failure == "second-index":
        monkeypatch.setattr(StoreIndex, "save", failed_save)
    else:
        monkeypatch.setattr(store_module, "complete_manifest_write", failed_completion)
    run_id = "original" if existing_run else "failed"
    if failure == "interrupt":
        with pytest.raises(KeyboardInterrupt):
            store.import_bundle(source, run_id, "revision-2", hold)
    else:
        assert not store.import_bundle(source, run_id, "revision-2", hold).success
    assert _indexes(store) == before
    reopened = LocalStore(store.store_root)
    assert reopened.list_runs() == ["original"]
    assert reopened.verify_integrity("original")["integrity_ok"]
    assert len(reopened.list_bundles_for_run("original")) == 1
    assert not reopened.list_bundles_for_run("failed")
    assert list((store.store_root / "quarantine").iterdir())


def test_failed_first_import_leaves_no_index_references(tmp_path, monkeypatch):
    source = tmp_path / "source.json"
    source.write_text('{"nodes": []}', encoding="utf-8")
    store = LocalStore(tmp_path / "store")

    def failed_completion(**kwargs):
        raise AtomicWriteError("simulated failure", kwargs["manifest_path"], "manifest")

    monkeypatch.setattr(store_module, "complete_manifest_write", failed_completion)
    result = store.import_bundle(source, "new", "revision-1", dict(status="none", reason="test", held_since="2026-09-10T00:00:00Z", authorized_by="test"))
    assert not result.success
    assert _indexes(store) == {}
    assert store.list_runs() == []


def test_failed_import_can_be_retried_without_losing_history(imported, monkeypatch):
    store, source, hold = imported
    complete = store_module.complete_manifest_write

    def fail_once(**kwargs):
        monkeypatch.setattr(store_module, "complete_manifest_write", complete)
        raise AtomicWriteError("simulated failure", kwargs["manifest_path"], "manifest")

    monkeypatch.setattr(store_module, "complete_manifest_write", fail_once)
    assert not store.import_bundle(source, "new", "revision-2", hold).success
    assert store.import_bundle(source, "new", "revision-2", hold).success
    assert store.list_runs() == ["new", "original"]
    assert store.verify_integrity("original")["integrity_ok"]


def test_pending_recovery_blocks_mutation_until_backup_is_restored(imported, monkeypatch):
    from hate.store import transaction

    store, source, hold = imported
    before = _indexes(store)
    write = transaction.atomic_write_bytes

    def failed_completion(**kwargs):
        raise AtomicWriteError("simulated completion failure", kwargs["manifest_path"], "manifest")

    def unavailable_restore(target, content, root):
        if target.parent == store.store_root / "indexes":
            raise AtomicWriteError("simulated restoration failure", target, "rename")
        return write(target, content, root)

    monkeypatch.setattr(store_module, "complete_manifest_write", failed_completion)
    monkeypatch.setattr(transaction, "atomic_write_bytes", unavailable_restore)
    with pytest.raises(LocalStoreError, match="recovery"):
        store.import_bundle(source, "failed", "revision-2", hold)
    pending = store.store_root / "migrations" / "pending-import"
    assert (pending / "journal.json").is_file()
    assert list((pending / "before").iterdir())
    with pytest.raises(LocalStoreError, match="recovery"):
        store.list_runs()
    monkeypatch.setattr(transaction, "atomic_write_bytes", write)
    reopened = LocalStore(store.store_root)
    assert _indexes(reopened) == before
    assert reopened.list_runs() == ["original"]
    assert not pending.exists()


def test_empty_run_id_does_not_create_recovery_work(imported):
    store, source, hold = imported
    before = _indexes(store)
    with pytest.raises(LocalStoreError):
        store.import_bundle(source, "", "revision-2", hold)
    assert _indexes(store) == before
    assert not (store.store_root / "migrations" / "pending-import").exists()


def test_commit_sync_uncertainty_preserves_complete_data_and_recovery_record(imported, monkeypatch):
    from hate.store import transaction

    store, source, hold = imported
    write = transaction.atomic_write_json

    def uncertain_commit(path, content, root):
        result = write(path, content, root)
        if content.get("state") == "committed":
            raise AtomicWriteError("simulated commit sync failure", path, "fsync", [{"published": True}])
        return result

    monkeypatch.setattr(transaction, "atomic_write_json", uncertain_commit)
    with pytest.raises(LocalStoreError, match="durability uncertain"):
        store.import_bundle(source, "new", "revision-2", hold)
    journal = store.store_root / "migrations" / "pending-import" / "journal.json"
    assert json.loads(journal.read_text(encoding="utf-8"))["state"] == "committed"
    monkeypatch.setattr(transaction, "atomic_write_json", write)
    reopened = LocalStore(store.store_root)
    assert reopened.list_runs() == ["new", "original"]
    assert reopened.verify_integrity("new")["integrity_ok"]
    assert not journal.exists()


def test_corrupt_backup_is_detected_before_restoring_any_index(imported):
    from hate.store.locking import store_lock
    from hate.store.transaction import ImportTransaction

    store, _, _ = imported
    with store_lock(store.store_root):
        transaction = ImportTransaction(store.store_root, store.store_root / "runs" / "pending" / "bundle-0000000000000000")
        transaction.__enter__()
        before = _indexes(store)
        backup = transaction.stage / "before" / "runs.jsonl"
        previous = backup.read_bytes()
        backup.write_bytes(b"corrupted backup")
    with pytest.raises(LocalStoreError, match="backup hash mismatch"):
        LocalStore(store.store_root)
    assert _indexes(store) == before
    assert backup.is_file()
    backup.write_bytes(previous)
    assert LocalStore(store.store_root).list_runs() == ["original"]
