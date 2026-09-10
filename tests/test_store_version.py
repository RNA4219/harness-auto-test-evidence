from __future__ import annotations

import json
from contextlib import contextmanager

import pytest

from hate.store import LocalStore, LocalStoreError
from hate.store.indexes import build_indexes_for_bundle
from hate.store.locking import store_lock
from hate.store.transaction import ImportTransaction, recover_pending_import


def _marker(**changes):
    return {
        "schema_version": "HATE/v1", "store_version": "1.0.0",
        "created_at": "2026-09-10T00:00:00Z", "producer_version": "test", **changes,
    }


def _snapshot(root):
    return {
        path.relative_to(root): (
            path.stat().st_size if path == root / "locks" / "store.lock"
            else path.read_bytes() if path.is_file() else None
        )
        for path in root.rglob("*")
    }


@pytest.mark.parametrize("changes", [
    {"schema_version": "HATE/v2"}, {"store_version": "2.0.0"}, {"store_version": "1.0.1"},
    {"store_version": None}, {"created_at": "2026-09-10"}, {"producer_version": " "},
])
def test_invalid_or_unsupported_marker_is_rejected_without_initializing_directories(tmp_path, changes):
    root = tmp_path / "store"
    root.mkdir()
    path = root / "store-version.json"
    path.write_text(json.dumps(_marker(**changes)), encoding="utf-8")
    before = _snapshot(root)
    with pytest.raises(LocalStoreError) as caught:
        LocalStore(root)
    assert caught.value.path == path and caught.value.diagnostics
    assert _snapshot(root) == before


@pytest.mark.parametrize("raw", [b"{broken", b"[]", b"{}", b"\xff", b'{"store_version": "2.0.0", "store_version": "1.0.0"}'])
def test_unreadable_or_ambiguous_marker_is_rejected_before_writes(tmp_path, raw):
    root = tmp_path / "store"
    root.mkdir()
    (root / "store-version.json").write_bytes(raw)
    before = _snapshot(root)
    with pytest.raises(LocalStoreError):
        LocalStore(root)
    assert _snapshot(root) == before


@pytest.fixture
def saved(tmp_path):
    source = tmp_path / "source.json"
    source.write_text('{"nodes": []}', encoding="utf-8")
    store = LocalStore(tmp_path / "store")
    hold = dict(status="none", reason="test", held_since="2026-09-10T00:00:00Z", authorized_by="test")
    result = store.import_bundle(source, "run-1", "revision-1", hold)
    assert result.success
    return store, source, hold, result


@pytest.mark.parametrize("operation", ["read", "import", "index-builder"])
def test_already_open_store_and_index_builder_recheck_version(saved, operation):
    store, source, hold, result = saved
    manifest = store.read_manifest("run-1").to_dict()
    (store.store_root / "store-version.json").write_text(json.dumps(_marker(store_version="2.0.0")), encoding="utf-8")
    before = _snapshot(store.store_root)
    with pytest.raises(LocalStoreError):
        if operation == "read":
            store.read_bundle(result.bundle_id)
        elif operation == "import":
            store.import_bundle(source, "new", "revision-2", hold)
        else:
            build_indexes_for_bundle(store.store_root, result.manifest_path.parent, manifest)
    assert _snapshot(store.store_root) == before


@pytest.mark.parametrize("operation", ["open", "read", "recover"])
def test_unknown_version_does_not_start_pending_recovery(saved, operation):
    store, _, _, result = saved
    version_path = store.store_root / "store-version.json"
    original_version = version_path.read_bytes()
    index_path = store.store_root / "indexes" / "runs.jsonl"
    original_index = index_path.read_bytes()
    with store_lock(store.store_root):
        transaction = ImportTransaction(store.store_root, result.manifest_path.parent, index_only=True)
        transaction.__enter__()
        index_path.write_bytes(b"")
    version_path.write_text(json.dumps(_marker(store_version="2.0.0")), encoding="utf-8")
    pending = _snapshot(store.store_root)
    with pytest.raises(LocalStoreError):
        if operation == "open":
            LocalStore(store.store_root)
        elif operation == "read":
            store.list_runs()
        else:
            with store_lock(store.store_root):
                recover_pending_import(store.store_root)
    assert _snapshot(store.store_root) == pending
    version_path.write_bytes(original_version)
    reopened = LocalStore(store.store_root)
    assert index_path.read_bytes() == original_index
    assert reopened.verify_integrity("run-1")["integrity_ok"]


def test_version_is_rechecked_after_lock_acquisition(saved, monkeypatch):
    from hate.store import locking

    store, _, _, _ = saved
    original_lock = locking.store_lock
    marker = store.store_root / "store-version.json"
    expected = None

    @contextmanager
    def changed_before_acquisition(root):
        nonlocal expected
        marker.write_text(json.dumps(_marker(store_version="2.0.0")), encoding="utf-8")
        expected = _snapshot(root)
        with original_lock(root) as outermost:
            yield outermost

    monkeypatch.setattr(locking, "store_lock", changed_before_acquisition)
    with pytest.raises(LocalStoreError):
        store.list_runs()
    assert _snapshot(store.store_root) == expected


@pytest.mark.parametrize("producer", ["", " ", "\ud800"])
def test_invalid_new_store_metadata_does_not_leave_partial_initialization(tmp_path, producer):
    root = tmp_path / "new-store"
    with pytest.raises(LocalStoreError):
        LocalStore(root, producer_version=producer)
    assert not root.exists()


def test_known_marker_preserves_existing_fields_and_creation_time(saved):
    store, _, _, _ = saved
    path = store.store_root / "store-version.json"
    marker = _marker(note="preserve this field")
    path.write_text(json.dumps(marker), encoding="utf-8")
    before = path.read_bytes()
    reopened = LocalStore(store.store_root, producer_version="new-reader")
    assert reopened.list_runs() == ["run-1"]
    assert path.read_bytes() == before


def test_raw_lock_does_not_bypass_store_version_check(saved):
    store, _, _, _ = saved
    with store_lock(store.store_root):
        (store.store_root / "store-version.json").write_text(json.dumps(_marker(store_version="2.0.0")), encoding="utf-8")
        before = _snapshot(store.store_root)
        with pytest.raises(LocalStoreError):
            store.list_runs()
        assert _snapshot(store.store_root) == before


def test_direct_transaction_rejects_unknown_version_before_staging(saved):
    store, _, _, result = saved
    (store.store_root / "store-version.json").write_text(json.dumps(_marker(store_version="2.0.0")), encoding="utf-8")
    before = _snapshot(store.store_root)
    with pytest.raises(LocalStoreError):
        with ImportTransaction(store.store_root, result.manifest_path.parent, index_only=True):
            pytest.fail("unknown version must not start a transaction")
    assert _snapshot(store.store_root) == before


@pytest.mark.parametrize("fail_write", [False, True])
def test_version_change_before_commit_preserves_pending_state_until_supported_reader(saved, monkeypatch, fail_write):
    from hate.store import local_store

    store, source, hold, _ = saved
    marker = store.store_root / "store-version.json"
    original_marker = marker.read_bytes()
    index_path = store.store_root / "indexes" / "runs.jsonl"
    original_index = index_path.read_bytes()
    original_write = local_store.complete_manifest_write
    pending = None

    def unexpected_reload():
        pytest.fail("unknown store version must not reload indexes")

    def change_version_after_write(**kwargs):
        nonlocal pending
        original_write(**kwargs)
        marker.write_text(json.dumps(_marker(store_version="2.0.0")), encoding="utf-8")
        pending = _snapshot(store.store_root)
        monkeypatch.setattr(store.index_manager, "load_all", unexpected_reload)
        if fail_write:
            raise OSError("write interrupted after version change")

    monkeypatch.setattr(local_store, "complete_manifest_write", change_version_after_write)
    with pytest.raises(LocalStoreError) as caught:
        store.import_bundle(source, "run-2", "revision-2", hold)
    assert caught.value.operation == "validate_store_version"
    assert _snapshot(store.store_root) == pending
    journal = store.store_root / "migrations" / "pending-import" / "journal.json"
    assert json.loads(journal.read_text(encoding="utf-8"))["state"] == "pending"
    marker.write_bytes(original_marker)
    reopened = LocalStore(store.store_root)
    assert index_path.read_bytes() == original_index
    assert reopened.list_runs() == ["run-1"]
    assert reopened.verify_integrity("run-1")["integrity_ok"]
    assert not journal.exists()
