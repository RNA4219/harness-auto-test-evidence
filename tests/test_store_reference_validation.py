from __future__ import annotations

import json

import pytest

from hate.store import LocalStore, LocalStoreError
from hate.store.atomic_write import compute_file_hash
from hate.store.doctor import diagnose_full_store
from hate.store.indexes import HardDQFinding, IndexEntry, StoreIndex


@pytest.mark.parametrize("filename", ["record.json", "record.JSON", "record.jsonl", "artifact.bin", "record"])
def test_lookup_verifies_raw_bytes_for_every_extension(tmp_path, filename):
    path = tmp_path / filename
    path.write_bytes(b"original")
    index = StoreIndex("evidence", tmp_path / "index.jsonl", tmp_path)
    index.add_entry("evidence-1", filename, compute_file_hash(path))
    assert index.lookup("evidence-1").key == "evidence-1"
    path.write_bytes(b"changed")
    with pytest.raises(HardDQFinding) as caught:
        index.lookup("evidence-1")
    assert caught.value.diagnostics[0]["issue"] == "hash_mismatch"
    assert path.read_bytes() == b"changed"


@pytest.mark.parametrize("failure", ["directory", "read-error"])
def test_unreadable_reference_is_a_data_quality_error(tmp_path, monkeypatch, failure):
    path = tmp_path / "record.json"
    path.write_bytes(b"original")
    index = StoreIndex("evidence", tmp_path / "index.jsonl", tmp_path)
    index.add_entry("evidence-1", path.name, compute_file_hash(path))
    if failure == "directory":
        path.unlink()
        path.mkdir()
    else:
        def unavailable(*args):
            raise PermissionError("simulated read error")
        monkeypatch.setattr(index, "_compute_record_hash", unavailable)
    with pytest.raises(HardDQFinding) as caught:
        index.lookup("evidence-1")
    assert caught.value.diagnostics[0]["issue"] in {"record_not_file", "record_unreadable"}


@pytest.mark.parametrize("verify", [False, True])
def test_lookup_rejects_inconsistent_cached_entry(tmp_path, verify):
    index = StoreIndex("evidence", tmp_path / "index.jsonl", tmp_path)
    index.entries["requested"] = IndexEntry("different", "record.json", "sha256:" + "0" * 64)
    with pytest.raises(HardDQFinding):
        index.lookup("requested", verify_record=verify)


def test_metadata_only_lookup_skips_file_access_but_keeps_reference_validation(tmp_path):
    index = StoreIndex("evidence", tmp_path / "index.jsonl", tmp_path)
    entry = index.add_entry("pending", "missing.bin", "sha256:" + "0" * 64)
    assert index.lookup("pending", verify_record=False) is entry
    with pytest.raises(HardDQFinding) as caught:
        index.lookup("pending")
    assert caught.value.diagnostics[0]["issue"] == "missing_record"


@pytest.mark.parametrize("options", [
    {"key": "\ud800"}, {"value": "\ud800.json"}, {"metadata": {"note": "\ud800"}},
])
def test_unencodable_entry_is_rejected_before_cache_or_disk_changes(tmp_path, options):
    index = StoreIndex("evidence", tmp_path / "index.jsonl", tmp_path)
    with pytest.raises(HardDQFinding) as caught:
        index.add_entry(**{"key": "new", "value": "record.json", "record_hash": "sha256:" + "0" * 64, **options})
    json.dumps(caught.value.to_record(), ensure_ascii=False, allow_nan=False).encode("utf-8")
    str(caught.value).encode("utf-8")
    assert not index.entries and not index.index_path.exists()


@pytest.fixture
def saved(tmp_path):
    source = tmp_path / "source.json"
    source.write_text('{"nodes": [{"id": "test-1", "kind": "test", "data": {"status": "passed"}}]}', encoding="utf-8")
    store = LocalStore(tmp_path / "store")
    hold = dict(status="none", reason="test", held_since="2026-09-10T00:00:00Z", authorized_by="test")
    result = store.import_bundle(source, "run-1", "revision-1", hold)
    assert result.success
    return store, source, hold, result


def _snapshot(store):
    return {path.relative_to(store.store_root): path.read_bytes() for path in store.store_root.rglob("*") if path.is_file()}


def _change_reference(store, index_type, change):
    index = next(item for item in store.index_manager._all_indexes() if item.index_type == index_type)
    index.load()
    entry = next(index.iter_entries())
    if change == "metadata":
        entry.metadata["bundle_id" if index_type == "runs" else "run_id"] = "other"
    else:
        original = store.store_root / entry.value
        alternate = original.with_name("alternate.json")
        alternate.write_bytes(original.read_bytes())
        entry.value = str(alternate.relative_to(store.store_root))
    index.save()


@pytest.mark.parametrize("index_type", ["runs", "bundles"])
@pytest.mark.parametrize("change", ["metadata", "filename"])
@pytest.mark.parametrize("operation", ["read", "manifest", "reimport"])
def test_local_readers_and_reimport_reject_inconsistent_reference(saved, index_type, change, operation):
    store, source, hold, result = saved
    _change_reference(store, index_type, change)
    before = _snapshot(store)
    with pytest.raises((LocalStoreError, HardDQFinding)):
        if operation == "reimport":
            store.import_bundle(source, "run-1", "revision-1", hold)
        elif operation == "read":
            store.read_bundle_by_run("run-1") if index_type == "runs" else store.read_bundle(result.bundle_id)
        else:
            store.read_manifest("run-1") if index_type == "runs" else store.read_manifest_by_bundle(result.bundle_id)
    assert _snapshot(store) == before


def test_artifact_alias_metadata_is_checked_during_integrity_and_reimport(saved):
    store, source, hold, _ = saved
    _change_reference(store, "artifacts", "metadata")
    before = _snapshot(store)
    assert not store.verify_integrity("run-1")["integrity_ok"]
    with pytest.raises(LocalStoreError):
        store.import_bundle(source, "run-1", "revision-1", hold)
    assert not diagnose_full_store(store).healthy
    assert _snapshot(store) == before


@pytest.mark.parametrize("index_type", ["runs", "bundles"])
def test_integrity_reports_bad_reference_without_throwing_away_diagnostics(saved, index_type):
    store, _, _, _ = saved
    _change_reference(store, index_type, "metadata")
    before = _snapshot(store)
    report = store.verify_integrity("run-1")
    assert not report["integrity_ok"] and report["diagnostics"]
    assert not diagnose_full_store(store).healthy
    assert _snapshot(store) == before


def test_hex_letter_case_does_not_change_digest_meaning(saved):
    store, source, hold, result = saved
    for index in store.index_manager._all_indexes():
        index.load()
        for entry in index.iter_entries():
            entry.hash = "sha256:" + entry.hash.split(":")[1].upper()
        index.save()
    before = _snapshot(store)
    assert store.read_bundle(result.bundle_id)
    assert store.verify_integrity("run-1")["integrity_ok"]
    assert store.import_bundle(source, "run-1", "revision-1", hold).success
    assert diagnose_full_store(store).healthy
    assert _snapshot(store) == before


def test_reimport_checks_current_run_copy_even_when_older_copy_is_valid(saved):
    store, source, hold, original = saved
    original_source = source.read_bytes()
    source.write_text('{"nodes": [{"id": "new", "kind": "test"}]}', encoding="utf-8")
    latest = store.import_bundle(source, "run-1", "revision-2", hold)
    assert latest.success and latest.bundle_id != original.bundle_id
    manifest = json.loads(latest.manifest_path.read_text(encoding="utf-8"))
    (latest.manifest_path.parent / f"{manifest['artifact_ids'][0]}.json").unlink()
    source.write_bytes(original_source)
    before = _snapshot(store)
    with pytest.raises(LocalStoreError):
        store.import_bundle(source, "run-1", "revision-1", hold)
    assert _snapshot(store) == before
