from __future__ import annotations

import json
from dataclasses import replace

import pytest

import hate.store.integrity as integrity
import hate.store.local_store as local_store
from hate.store import LocalStore, LocalStoreError


@pytest.fixture
def imported(tmp_path):
    store = LocalStore(tmp_path / "store")
    source = tmp_path / "source.json"
    original = {"revision": 1, "nodes": [{"id": "test:one", "kind": "test_result", "status": "pass"}]}
    source.write_text(json.dumps(original), encoding="utf-8")
    hold = dict(status="none", reason="test", held_since="2026-09-10T00:00:00Z", authorized_by="test")
    first = store.import_bundle(source, "run-1", "revision-1", hold)
    assert first.success
    return store, source, original, hold, first


def _snapshot(store):
    return {
        path.relative_to(store.store_root): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in store.store_root.rglob("*") if path.is_file() and path.name != "store.lock"
    }


def _force_short_id_collision(monkeypatch, first, *, artifact=False):
    # 内容とSHA256全体は変えず、ID割当だけを衝突させて境界を検証する。
    prepare = local_store.prepare_bundle
    manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))
    original_artifact_id = manifest["artifact_ids"][0]

    def colliding_id(data, source):
        prepared = prepare(data, source)
        if artifact:
            node = next(iter(prepared.artifacts.values()))
            digest = next(iter(prepared.content_hashes.values()))
            return replace(prepared, artifacts={original_artifact_id: node}, content_hashes={original_artifact_id: digest})
        return replace(prepared, bundle_id=first.bundle_id)

    monkeypatch.setattr(local_store, "prepare_bundle", colliding_id)
    monkeypatch.setattr(integrity, "prepare_bundle", colliding_id)


@pytest.mark.parametrize("run_id", ["run-1", "run-2"])
@pytest.mark.parametrize("replacement", [2, True])
def test_bundle_short_id_collision_does_not_reuse_or_publish_different_content(imported, monkeypatch, run_id, replacement):
    store, source, original, hold, first = imported
    _force_short_id_collision(monkeypatch, first)
    source.write_text(json.dumps({**original, "revision": replacement}), encoding="utf-8")
    before = _snapshot(store)
    with pytest.raises(LocalStoreError) as caught:
        store.import_bundle(source, run_id, "revision-2", hold)
    assert any(item.get("issue") == "bundle_id_collision" for item in caught.value.diagnostics)
    assert _snapshot(store) == before
    assert store.read_bundle_by_run("run-1") == original
    assert store.verify_integrity("run-1")["integrity_ok"]
    assert not list((store.store_root / "quarantine").iterdir())


@pytest.mark.parametrize("run_id", ["run-1", "run-2"])
def test_artifact_short_id_collision_does_not_invalidate_previous_history(imported, monkeypatch, run_id):
    store, source, original, hold, first = imported
    _force_short_id_collision(monkeypatch, first, artifact=True)
    replacement = {**original, "nodes": [{**original["nodes"][0], "status": "failed"}]}
    source.write_text(json.dumps(replacement), encoding="utf-8")
    before = _snapshot(store)
    with pytest.raises(LocalStoreError) as caught:
        store.import_bundle(source, run_id, "revision-2", hold)
    assert any(item.get("issue") == "artifact_id_collision" for item in caught.value.diagnostics)
    assert _snapshot(store) == before
    assert store.verify_integrity("run-1")["integrity_ok"]
    assert store.list_bundles_for_run("run-1") == [first.bundle_id]
    assert not list((store.store_root / "quarantine").iterdir())


def test_equivalent_canonical_bundle_can_still_be_imported_with_another_json_key_order(imported):
    store, source, original, hold, first = imported
    reordered = {"nodes": [{key: node[key] for key in reversed(node)} for node in original["nodes"]], "revision": 1}
    source.write_text(json.dumps(reordered), encoding="utf-8")
    before = _snapshot(store)
    assert store.import_bundle(source, "run-1", "revision-1", hold).success
    assert _snapshot(store) == before
    second = store.import_bundle(source, "run-2", "revision-2", hold)
    assert second.success and second.bundle_id == first.bundle_id
    assert store.verify_integrity("run-1")["integrity_ok"]
    assert store.verify_integrity("run-2")["integrity_ok"]


def test_shared_identical_artifact_still_allows_a_different_bundle(imported):
    store, source, original, hold, first = imported
    source.write_text(json.dumps({**original, "revision": 2}), encoding="utf-8")
    second = store.import_bundle(source, "run-2", "revision-2", hold)
    assert second.success and second.bundle_id != first.bundle_id
    assert store.read_manifest("run-1").artifact_ids == store.read_manifest("run-2").artifact_ids
    assert store.verify_integrity("run-1")["integrity_ok"]
    assert store.verify_integrity("run-2")["integrity_ok"]


@pytest.mark.parametrize("member", ["bundle", "artifact"])
def test_unverifiable_existing_identity_is_not_replaced_by_new_import(imported, member):
    store, source, original, hold, first = imported
    if member == "bundle":
        missing = first.manifest_path.parent / "qeg-bundle.json"
    else:
        missing = first.manifest_path.parent / f"{store.read_manifest('run-1').artifact_ids[0]}.json"
        source.write_text(json.dumps({**original, "revision": 2}), encoding="utf-8")
    missing.unlink()
    before = _snapshot(store)
    with pytest.raises(LocalStoreError):
        store.import_bundle(source, "run-2", "revision-2", hold)
    assert _snapshot(store) == before
    assert not (store.store_root / "runs" / "run-2").exists()
    assert not list((store.store_root / "quarantine").iterdir())


def test_one_import_can_share_artifacts_from_several_existing_copies(imported):
    store, source, original, hold, _ = imported
    other_nodes = [{"id": f"test:other-{i}", "kind": "test_result", "status": "pass"} for i in range(16)]
    source.write_text(json.dumps({"nodes": other_nodes}), encoding="utf-8")
    second = store.import_bundle(source, "run-2", "revision-2", hold)
    assert second.success
    mixed_nodes = [*original["nodes"], *other_nodes]
    source.write_text(json.dumps({"nodes": mixed_nodes}), encoding="utf-8")
    assert store.import_bundle(source, "run-3", "revision-3", hold).success
    assert len(store.read_manifest("run-3").artifact_ids) == len(mixed_nodes)
    assert all(store.verify_integrity(run)["integrity_ok"] for run in ("run-1", "run-2", "run-3"))
