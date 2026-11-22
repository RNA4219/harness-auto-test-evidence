from __future__ import annotations

import json

import pytest

from hate.store import LocalStore, LocalStoreError


@pytest.fixture
def imported(tmp_path):
    source = tmp_path / "source.json"
    source.write_text(json.dumps({
        "schema_version": "HATE/v1", "nodes": [{"id": "test-1", "kind": "test_result", "status": "pass"}],
    }), encoding="utf-8")
    store = LocalStore(tmp_path / "store")
    hold = {"status": "none", "reason": "test", "held_since": "2026-09-10T00:00:00Z", "authorized_by": "test"}
    result = store.import_bundle(source, "run-1", "revision-1", hold)
    assert result.success
    return store, source, hold, result


@pytest.mark.parametrize("operation", ["read_bundle", "read_bundle_by_run", "read_manifest", "read_manifest_by_bundle"])
def test_reopened_store_reads_existing_indexes_without_prior_list_call(imported, operation):
    store, _, _, result = imported
    reopened = LocalStore(store.store_root)
    key = result.bundle_id if operation in {"read_bundle", "read_manifest_by_bundle"} else "run-1"
    assert getattr(reopened, operation)(key)


def test_integrity_check_does_not_write_any_store_file(imported):
    store, _, _, _ = imported

    def snapshot():
        return {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in store.store_root.rglob("*") if path.is_file()}

    before = snapshot()
    assert store.verify_integrity("run-1")["integrity_ok"]
    assert snapshot() == before


def test_adding_another_run_does_not_invalidate_previous_run(imported):
    store, source, hold, _ = imported
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["nodes"][0]["status"] = "failed"
    source.write_text(json.dumps(payload), encoding="utf-8")
    assert store.import_bundle(source, "run-2", "revision-2", hold).success
    assert store.verify_integrity("run-1")["integrity_ok"]
    assert store.verify_integrity("run-2")["integrity_ok"]


@pytest.mark.parametrize("change", ["missing", "modified"])
def test_integrity_check_detects_canonical_bundle_damage(imported, change):
    store, _, _, result = imported
    bundle = result.manifest_path.parent / "qeg-bundle.json"
    if change == "missing":
        bundle.unlink()
    else:
        bundle.write_text('{"changed": true}', encoding="utf-8")
    report = store.verify_integrity("run-1")
    assert not report["integrity_ok"]
    assert any(item["issue"] in {"missing_bundle", "bundle_hash_mismatch"} for item in report["diagnostics"])


def test_integrity_check_detects_missing_artifact_hash(imported):
    store, _, _, result = imported
    data = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    data["content_hashes"] = {}
    result.manifest_path.write_text(json.dumps(data), encoding="utf-8")
    report = store.verify_integrity("run-1")
    assert not report["integrity_ok"]
    assert any(item["issue"] == "missing_artifact_hash" for item in report["diagnostics"])


def test_integrity_check_detects_removed_artifact_index_entry(imported):
    store, _, _, _ = imported
    store.index_manager.artifacts_index.index_path.write_text("", encoding="utf-8")
    report = store.verify_integrity("run-1")
    assert not report["integrity_ok"]
    assert any(item["issue"] == "missing_index_entry" for item in report["diagnostics"])


@pytest.mark.parametrize("invalid", [b"[]", b"\xff", b"{broken", b'{"number": NaN}'])
def test_invalid_bundle_input_raises_store_error_before_import(imported, invalid):
    store, source, hold, _ = imported
    source.write_bytes(invalid)
    with pytest.raises(LocalStoreError):
        store.import_bundle(source, "run-invalid", "revision-2", hold)
    assert not (store.store_root / "runs" / "run-invalid").exists()


def test_same_content_imported_for_another_run_keeps_both_runs_valid(imported):
    store, source, hold, _ = imported
    assert store.import_bundle(source, "run-2", "revision-2", hold).success
    assert store.verify_integrity("run-1")["integrity_ok"]
    assert store.verify_integrity("run-2")["integrity_ok"]
