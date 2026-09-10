from __future__ import annotations

import json

import pytest

from hate.schema_resources import read_schema, validate_schema_instance
from hate.store import LocalStore, LocalStoreError, StoreManifest
from hate.store.atomic_write import AtomicWriteError, complete_manifest_write, is_complete_manifest


@pytest.fixture
def imported(tmp_path):
    source = tmp_path / "source.json"
    source.write_text(json.dumps({"schema_version": "HATE/v1", "nodes": [{"kind": "test_result", "status": "pass"}]}), encoding="utf-8")
    store = LocalStore(tmp_path / "store")
    hold = dict(status="none", reason="test", held_since="2026-09-10T00:00:00Z", authorized_by="test")
    result = store.import_bundle(source, "run-1", "revision-1", hold)
    assert result.success
    return store, source, hold, result


def snapshot(store):
    return {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in store.store_root.rglob("*") if path.is_file()}


@pytest.mark.parametrize("raw", [b"[]", b"null", b"1", b"\xff", b"{broken", b'{"completed": true}'])
def test_completion_check_requires_valid_manifest(tmp_path, raw):
    path = tmp_path / "store-manifest.json"
    path.write_bytes(raw)
    assert not is_complete_manifest(path)


def test_invalid_manifest_cannot_be_published_as_complete(imported):
    store, _, _, result = imported
    before = snapshot(store)
    with pytest.raises(AtomicWriteError, match="Invalid store manifest"):
        complete_manifest_write(result.manifest_path, {"completed": False}, store.store_root, [])
    assert snapshot(store) == before


@pytest.mark.parametrize("field,value", [
    ("completed", "true"), ("run_id", " "), ("artifact_ids", "artifact"),
    ("content_hashes", []), ("index_hashes", {"runs": "bad"}), ("created_at", "yesterday"),
    ("schema_versions", {"core": "HATE/v1", "store": "1", "bundle": 7}),
])
def test_invalid_manifest_fields_are_store_errors(imported, field, value):
    store, _, _, result = imported
    data = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    data[field] = value
    with pytest.raises(LocalStoreError):
        StoreManifest.from_dict(data)
    result.manifest_path.write_text(json.dumps(data), encoding="utf-8")
    assert not is_complete_manifest(result.manifest_path)
    with pytest.raises(LocalStoreError):
        store.read_manifest("run-1")


@pytest.mark.parametrize("field,value", [
    ("status", "unknown"), ("status", None), ("reason", " "), ("authorized_by", " "),
    ("authorized_by", 10), ("held_since", "2026-09-10"), ("held_since", "2026-02-30T00:00:00Z"),
])
def test_invalid_hold_rejected_before_import(imported, field, value):
    store, source, hold, _ = imported
    hold[field] = value
    before = snapshot(store)
    with pytest.raises(LocalStoreError):
        store.import_bundle(source, "run-invalid", "revision-2", hold)
    assert snapshot(store) == before
    assert not (store.store_root / "runs" / "run-invalid").exists()


@pytest.mark.parametrize("options", [
    {"source_version": " "}, {"retention_policy_id": ""}, {"sourceRefs": []}, {"sourceRefs": [" "]},
])
def test_invalid_metadata_is_not_replaced_with_defaults(imported, options):
    store, source, hold, _ = imported
    before = snapshot(store)
    with pytest.raises(LocalStoreError):
        store.import_bundle(source, "run-invalid", legal_hold=hold, **{"source_version": "revision-2", **options})
    assert snapshot(store) == before


@pytest.mark.parametrize("status,reason,actor", [
    ("other", "test", "actor"), ("active", " ", "actor"), ("released", "test", " "),
])
def test_invalid_hold_update_preserves_manifest(imported, status, reason, actor):
    store, _, _, _ = imported
    before = snapshot(store)
    with pytest.raises(LocalStoreError):
        store.update_legal_hold("run-1", status, reason, actor)
    assert snapshot(store) == before


def test_writer_and_hold_release_match_packaged_schema(imported):
    store, source, hold, result = imported
    schema = read_schema("store-manifest.schema.json")
    assert not validate_schema_instance(json.loads(result.manifest_path.read_text(encoding="utf-8")), schema)
    store.update_legal_hold("run-1", "active", "review", "actor")
    store.update_legal_hold("run-1", "released", "review complete", "actor")
    assert not validate_schema_instance(json.loads(result.manifest_path.read_text(encoding="utf-8")), schema)
    source.write_text('{"nodes": []}', encoding="utf-8")
    empty = store.import_bundle(source, "run-empty", "revision-2", hold)
    assert empty.success
    data = json.loads(empty.manifest_path.read_text(encoding="utf-8"))
    assert data["artifact_ids"] == []
    assert not validate_schema_instance(data, schema)


@pytest.mark.parametrize("change", ["flag_only", "incomplete", "missing_bundle", "artifact", "missing_hash", "erased_list", "bundle_index", "bad_index"])
def test_reimport_validates_existing_copy_without_overwriting_it(imported, change):
    store, source, hold, result = imported
    data = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    if change == "flag_only":
        result.manifest_path.write_text('{"completed": true}', encoding="utf-8")
    elif change == "incomplete":
        data["completed"] = False
        data["import_status"]["phase"] = "importing"
        result.manifest_path.write_text(json.dumps(data), encoding="utf-8")
    elif change == "missing_bundle":
        (result.manifest_path.parent / "qeg-bundle.json").unlink()
    elif change == "artifact":
        (result.manifest_path.parent / f"{data['artifact_ids'][0]}.json").write_text("{}", encoding="utf-8")
    elif change in {"missing_hash", "erased_list"}:
        data["content_hashes"] = {}
        if change == "erased_list":
            data["artifact_ids"] = []
        result.manifest_path.write_text(json.dumps(data), encoding="utf-8")
    elif change == "bundle_index":
        store.index_manager.bundles_index.index_path.write_text("", encoding="utf-8")
    else:
        store.index_manager.bundles_index.index_path.write_text("invalid", encoding="utf-8")
    before = snapshot(store)
    with pytest.raises(LocalStoreError):
        store.import_bundle(source, "run-1", "revision-1", hold)
    assert snapshot(store) == before


@pytest.mark.parametrize("by_run", [False, True])
def test_unfinished_manifest_cannot_be_read_as_a_bundle(imported, by_run):
    store, _, _, result = imported
    data = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    data["completed"] = False
    data["import_status"]["phase"] = "importing"
    result.manifest_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(LocalStoreError, match="not complete"):
        store.read_bundle_by_run("run-1") if by_run else store.read_bundle(result.bundle_id)


def test_historical_reimport_does_not_reset_latest_run_alias(imported):
    store, source, hold, first = imported
    old_source = source.read_bytes()
    source.write_text('{"nodes": []}', encoding="utf-8")
    latest = store.import_bundle(source, "run-1", "revision-2", hold)
    source.write_bytes(old_source)
    assert store.import_bundle(source, "run-1", "revision-1", hold).bundle_id == first.bundle_id
    assert store.read_manifest("run-1").bundle_id == latest.bundle_id


def test_equivalent_json_key_orders_do_not_invalidate_shared_bundle(imported):
    store, source, hold, first = imported
    data = json.loads(source.read_text(encoding="utf-8"))
    data["nodes"] = [dict(reversed(list(node.items()))) for node in data["nodes"]]
    source.write_text(json.dumps(dict(reversed(list(data.items())))), encoding="utf-8")
    second = store.import_bundle(source, "run-2", "revision-2", hold)
    assert first.bundle_id == second.bundle_id
    assert (first.manifest_path.parent / "qeg-bundle.json").read_bytes() != (second.manifest_path.parent / "qeg-bundle.json").read_bytes()
    assert store.verify_integrity("run-1")["integrity_ok"]
    assert store.verify_integrity("run-2")["integrity_ok"]
