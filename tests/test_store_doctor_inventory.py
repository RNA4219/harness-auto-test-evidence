from __future__ import annotations

import json

import pytest

from hate.store import LocalStore
from hate.store.doctor import diagnose_bundle, diagnose_full_store, diagnose_run


@pytest.fixture
def imported(tmp_path):
    store = LocalStore(tmp_path / "store")
    source = tmp_path / "source.json"
    source.write_text('{"nodes": [{"kind": "test_result", "status": "pass"}]}', encoding="utf-8")
    hold = dict(status="none", reason="test", held_since="2026-09-10T00:00:00Z", authorized_by="test")
    first = store.import_bundle(source, "run-1", "revision-1", hold)
    second = store.import_bundle(source, "run-2", "revision-2", hold)
    assert first.success and second.success
    return store, first, second


def snapshot(store):
    return {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in store.store_root.rglob("*") if path.is_file()}


def issues(report):
    return {item.diagnostics.get("issue") for item in report.findings}


def test_full_doctor_does_not_misclassify_store_infrastructure(imported, tmp_path):
    store, _, _ = imported
    before = snapshot(store)
    assert diagnose_full_store(store).findings == []
    assert snapshot(store) == before
    assert diagnose_full_store(LocalStore(tmp_path / "empty")).findings == []


@pytest.mark.parametrize("raw", [b"[]", b"null", b"\xff", b"{broken", b'{"completed": true}'])
def test_bad_manifest_becomes_finding_and_other_copies_are_still_checked(imported, raw):
    store, first, second = imported
    first.manifest_path.write_bytes(raw)
    data = json.loads(second.manifest_path.read_text(encoding="utf-8"))
    (second.manifest_path.parent / f"{data['artifact_ids'][0]}.json").unlink()
    before = snapshot(store)
    report = diagnose_full_store(store)
    assert not report.healthy
    assert {"invalid_manifest", "missing_artifact"} <= issues(report)
    assert snapshot(store) == before


@pytest.mark.parametrize("scope", ["run", "full"])
@pytest.mark.parametrize("state", ["incomplete", "missing_manifest", "unindexed"])
def test_legacy_incomplete_and_unindexed_copies_are_visible(imported, scope, state):
    store, first, _ = imported
    if state == "incomplete":
        data = json.loads(first.manifest_path.read_text(encoding="utf-8"))
        data["completed"] = False
        data["import_status"]["phase"] = "importing"
        first.manifest_path.write_text(json.dumps(data), encoding="utf-8")
    elif state == "missing_manifest":
        first.manifest_path.unlink()
    else:
        store.index_manager.runs_index.index_path.write_text("", encoding="utf-8")
        store.index_manager.bundles_index.index_path.write_text("", encoding="utf-8")
    before = snapshot(store)
    report = diagnose_run(store, "run-1") if scope == "run" else diagnose_full_store(store)
    expected = {"incomplete": "manifest_not_complete", "missing_manifest": "invalid_manifest", "unindexed": "missing_index_entry"}[state]
    assert expected in issues(report)
    assert not report.healthy
    assert snapshot(store) == before


@pytest.mark.parametrize("name", ["runs", "bundles", "artifacts", "evidence", "risks", "requirements", "source_refs"])
def test_one_corrupt_index_does_not_abort_full_doctor(imported, name):
    store, first, _ = imported
    index = next(index for index in store.index_manager._all_indexes() if index.index_type == name)
    index.index_path.write_bytes(b"not json\n")
    first.manifest_path.unlink()
    before = snapshot(store)
    report = diagnose_full_store(store)
    assert {"index_unreadable", "invalid_manifest"} <= issues(report)
    assert snapshot(store) == before


def test_missing_indexed_bundle_file_is_reported(imported):
    store, _, second = imported
    (second.manifest_path.parent / "qeg-bundle.json").unlink()
    report = diagnose_full_store(store)
    assert {"index_record_unreadable", "missing_bundle"} <= issues(report)


def test_unindexed_directory_without_a_manifest_is_reported(imported):
    store, _, _ = imported
    orphan = store.store_root / "runs" / "legacy" / "bundle-0000000000000000"
    orphan.mkdir(parents=True)
    report = diagnose_full_store(store)
    assert {"missing_index_entry", "invalid_manifest"} <= issues(report)
    assert any(item.diagnostics.get("run_id") == "legacy" for item in report.findings)


def test_missing_artifact_hash_and_index_are_reported(imported):
    store, first, _ = imported
    data = json.loads(first.manifest_path.read_text(encoding="utf-8"))
    data["content_hashes"] = {}
    first.manifest_path.write_text(json.dumps(data), encoding="utf-8")
    store.index_manager.artifacts_index.index_path.write_text("", encoding="utf-8")
    report = diagnose_full_store(store)
    assert {"missing_artifact_hash", "missing_index_entry"} <= issues(report)


def test_unknown_bundle_returns_actionable_diagnosis(imported):
    store, _, _ = imported
    report = diagnose_bundle(store, "bundle-0000000000000000")
    assert not report.healthy
    assert "bundle_unresolved" in issues(report)
