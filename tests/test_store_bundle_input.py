from __future__ import annotations

import json
from pathlib import Path

import pytest

from hate.store import LocalStore, LocalStoreError
from hate.store.atomic_write import compute_file_hash
from hate.store.doctor import diagnose_full_store
from hate.store.replay import replay_bundle


@pytest.fixture
def empty_store(tmp_path):
    store = LocalStore(tmp_path / "store")
    source = tmp_path / "source.json"
    hold = dict(status="none", reason="test", held_since="2026-09-10T00:00:00Z", authorized_by="test")
    return store, source, hold


def _snapshot(store):
    return {path.relative_to(store.store_root): path.read_bytes() for path in store.store_root.rglob("*") if path.is_file()}


@pytest.mark.parametrize("raw", [
    '{"nodes": [], "nodes": [{"kind": "test"}]}',
    '{"nodes": [{"kind": "test", "data": {"status": "failed", "status": "passed"}}]}',
    '{"nodes": [], "value": 1e999}',
    '{"nodes": [], "value": -1e999}',
    '{"nodes": [], "value": 1e-999}',
    '{"nodes": [], "value": -1e-999}',
    '{"nodes": [], "value": "\\ud800"}',
])
def test_ambiguous_or_unrepresentable_json_is_rejected_before_writes(empty_store, raw):
    store, source, hold = empty_store
    source.write_text(raw, encoding="utf-8")
    before = _snapshot(store)
    with pytest.raises(LocalStoreError):
        store.import_bundle(source, "bad", "revision-1", hold)
    assert _snapshot(store) == before
    assert source.read_text(encoding="utf-8") == raw


@pytest.mark.parametrize("payload", [
    {"nodes": None}, {"nodes": {}}, {"nodes": "wrong"}, {"nodes": [None]},
    {"nodes": [[]]}, {"nodes": [{}]}, {"nodes": [{"kind": []}]},
    {"nodes": [{"kind": " "}]}, {"nodes": [{"id": "", "kind": "test"}]},
    {"nodes": [{"id": 7, "kind": "test"}]}, {"nodes": [{"kind": "test", "data": []}]},
    {"nodes": [{"kind": "test", "payload": None}]},
    {"nodes": [{"kind": "test"}, {"kind": "test"}]},
    {"nodes": [{"id": "same", "kind": "test"}, {"id": "same", "kind": "coverage"}]},
    {"nodes": [], "edges": None},
    {"nodes": [], "metadata": []},
])
def test_invalid_node_structure_is_rejected_before_transaction(empty_store, payload):
    store, source, hold = empty_store
    source.write_text(json.dumps(payload), encoding="utf-8")
    before = _snapshot(store)
    with pytest.raises(LocalStoreError) as caught:
        store.import_bundle(source, "bad", "revision-1", hold)
    assert caught.value.diagnostics
    assert _snapshot(store) == before


def _qeg_bundle():
    source = Path(__file__).resolve().parents[1] / "fixtures/golden/p0b-qeg-minimal/expected/qeg-bundle.json"
    return json.loads(source.read_text(encoding="utf-8"))


@pytest.mark.parametrize("change", ["version", "version-missing", "metadata-missing", "required", "node", "edge", "completeness"])
def test_declared_qeg_bundle_must_match_public_schema(empty_store, change):
    store, source, hold = empty_store
    data = _qeg_bundle()
    if change == "version":
        data["metadata"]["qegVersion"] = "HATE/v-next"
    elif change == "version-missing":
        del data["metadata"]["qegVersion"]
    elif change == "metadata-missing":
        del data["metadata"]
    elif change == "required":
        del data["metadata"]["runAttempt"]
    elif change == "node":
        del data["nodes"][0]["sourceRefs"]
    elif change == "edge":
        data["edges"][0]["traceability"]["confidence"] = "unknown"
    else:
        data["completeness"]["partial"] = "false"
    source.write_text(json.dumps(data), encoding="utf-8")
    before = _snapshot(store)
    with pytest.raises(LocalStoreError) as caught:
        store.import_bundle(source, "bad", "revision-1", hold)
    assert any(item["issue"] == "invalid_qeg_bundle" for item in caught.value.diagnostics)
    assert _snapshot(store) == before


def test_real_qeg_bundle_round_trips_without_rewriting_nodes(empty_store):
    store, source, hold = empty_store
    data = _qeg_bundle()
    source.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    source_bytes = source.read_bytes()
    result = store.import_bundle(source, "local-run", "revision-1", hold)
    assert result.success
    assert store.read_bundle(result.bundle_id) == data
    assert store.verify_integrity("local-run")["integrity_ok"]
    assert replay_bundle(store, result.bundle_id).integrity_ok
    assert source.read_bytes() == source_bytes


@pytest.mark.parametrize("data", [
    {}, {"nodes": []}, {"nodes": [{"kind": "custom", "data": {"note": "日本語😀"}}]},
    {"nodes": [{"kind": "test", "data": {"status": "passed", "duration": 1e-12}}]},
])
def test_legacy_structural_input_remains_lossless(empty_store, data):
    store, source, hold = empty_store
    source.write_text(json.dumps(data), encoding="utf-8")
    result = store.import_bundle(source, "legacy", "revision-1", hold)
    assert result.success
    assert store.read_bundle(result.bundle_id) == data


@pytest.mark.parametrize("field", ["source_version", "producer_version", "hold_author"])
def test_unserializable_metadata_is_rejected_before_transaction(empty_store, field):
    store, source, hold = empty_store
    source.write_text('{"nodes": []}', encoding="utf-8")
    version = "revision-1"
    if field == "source_version":
        version = "\ud800"
    elif field == "producer_version":
        store.producer_version = "\ud800"
    else:
        hold["authorized_by"] = "\ud800"
    before = _snapshot(store)
    with pytest.raises(LocalStoreError):
        store.import_bundle(source, "bad", version, hold)
    assert _snapshot(store) == before


def test_legacy_saved_qeg_violation_is_diagnosed_and_not_returned_as_valid_data(empty_store):
    store, source, hold = empty_store
    data = _qeg_bundle()
    source.write_text(json.dumps(data), encoding="utf-8")
    result = store.import_bundle(source, "old", "revision-1", hold)
    assert result.success
    path = result.manifest_path.parent / "qeg-bundle.json"
    data["completeness"]["partial"] = "false"
    path.write_text(json.dumps(data), encoding="utf-8")
    # 保存形式が緩かった旧データを表す。raw hashは読めるがschemaは不正。
    for index, key in ((store.index_manager.runs_index, "old"), (store.index_manager.bundles_index, result.bundle_id)):
        index.load()
        index.entries[key].hash = compute_file_hash(path)
        index.save()
    before = _snapshot(store)
    with pytest.raises(LocalStoreError) as caught:
        store.read_bundle_by_run("old")
    assert any(item["issue"] == "invalid_qeg_bundle" for item in caught.value.diagnostics)
    report = replay_bundle(store, result.bundle_id)
    assert not report.integrity_ok
    assert any(item["issue"] == "invalid_qeg_bundle" for item in report.diagnostics)
    assert diagnose_full_store(store).findings
    assert _snapshot(store) == before
