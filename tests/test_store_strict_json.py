from __future__ import annotations

import json

import pytest

from hate.store import LocalStore, LocalStoreError
from hate.store.atomic_write import is_complete_manifest
from hate.store.doctor import diagnose_full_store
from hate.store.indexes import IndexLookupError
from hate.store.locking import store_lock
from hate.store.transaction import ImportTransaction


@pytest.fixture
def saved(tmp_path):
    source = tmp_path / "source.json"
    source.write_text('{"nodes": []}', encoding="utf-8")
    store = LocalStore(tmp_path / "store")
    hold = dict(status="none", reason="test", held_since="2026-09-10T00:00:00Z", authorized_by="test")
    result = store.import_bundle(source, "run-1", "revision-1", hold)
    assert result.success
    return store, result.manifest_path


def _snapshot(store):
    return {path.relative_to(store.store_root): path.read_bytes() for path in store.store_root.rglob("*") if path.is_file()}


@pytest.mark.parametrize("scope", ["top", "nested"])
def test_manifest_duplicate_fields_are_not_complete_or_readable(saved, scope):
    store, path = saved
    data = json.loads(path.read_text(encoding="utf-8"))
    if scope == "top":
        content = '{"completed": false,' + json.dumps(data)[1:]
    else:
        content = json.dumps(data).replace('"status": "none"', '"status": "active", "status": "none"')
    path.write_text(content, encoding="utf-8")
    before = _snapshot(store)
    assert not is_complete_manifest(path)
    with pytest.raises(LocalStoreError, match="duplicate JSON"):
        store.read_manifest("run-1")
    assert diagnose_full_store(store).findings
    assert _snapshot(store) == before


@pytest.mark.parametrize("scope", ["top", "nested"])
def test_duplicate_fields_in_index_row_preserve_disk_and_loaded_cache(saved, scope):
    store, _ = saved
    index = store.index_manager.runs_index
    index.load()
    previous = dict(index.entries)
    data = json.loads(index.index_path.read_text(encoding="utf-8"))
    if scope == "top":
        content = '{"key": "earlier",' + json.dumps(data)[1:]
    else:
        content = json.dumps(data).replace('"bundle_id":', '"bundle_id": "earlier", "bundle_id":')
    index.index_path.write_text(content + "\n", encoding="utf-8")
    before = _snapshot(store)
    with pytest.raises(IndexLookupError) as caught:
        index.load()
    assert "duplicate JSON" in caught.value.message
    assert caught.value.diagnostics[0]["line_number"] == 1
    assert index.entries == previous
    assert _snapshot(store) == before


def test_ambiguous_recovery_journal_retains_backup_until_record_is_restored(saved):
    store, manifest_path = saved
    before = _snapshot(store)
    with store_lock(store.store_root):
        transaction = ImportTransaction(store.store_root, manifest_path.parent, index_only=True)
        transaction.__enter__()
        path = transaction.stage / "journal.json"
        original = path.read_bytes()
        path.write_text('{"version": 2,' + original.decode("utf-8")[1:], encoding="utf-8")
    pending = _snapshot(store)
    with pytest.raises(LocalStoreError, match="duplicate JSON"):
        LocalStore(store.store_root)
    assert _snapshot(store) == pending
    path.write_bytes(original)
    reopened = LocalStore(store.store_root)
    assert reopened.verify_integrity("run-1")["integrity_ok"]
    assert all((store.store_root / name).read_bytes() == content for name, content in before.items())


@pytest.mark.parametrize("content", ['{broken', '[]', '{"nodes": [], "nodes": []}'])
def test_doctor_retains_bad_bundle_path_without_diagnostic_argument_collision(saved, content):
    store, manifest_path = saved
    path = manifest_path.parent / "qeg-bundle.json"
    path.write_text(content, encoding="utf-8")
    before = _snapshot(store)
    findings = diagnose_full_store(store).findings
    affected = [item for item in findings if item.diagnostics.get("issue") == "bundle_unreadable"]
    assert affected and all(item.path == str(path) for item in affected)
    assert _snapshot(store) == before
