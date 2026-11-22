from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime

import pytest

from hate.store import LocalStore
from hate.store.doctor import diagnose_bundle, diagnose_full_store, diagnose_run
from hate.store.replay import build_store_replay_report, replay_bundle


@pytest.fixture
def imported(tmp_path):
    store = LocalStore(tmp_path / "store")
    source = tmp_path / "source.json"
    source.write_text('{"nodes": [{"id": "first", "kind": "test_result", "status": "pass"}]}', encoding="utf-8")
    hold = dict(status="none", reason="test", held_since="2026-09-10T00:00:00Z", authorized_by="test")
    first = store.import_bundle(source, "run-1", "revision", hold)
    second = store.import_bundle(source, "run-2", "revision", hold)
    source.write_text('{"nodes": [{"id": "second", "kind": "test_result", "status": "pass"}]}', encoding="utf-8")
    third = store.import_bundle(source, "other", "revision", hold)
    assert first.success and second.success and third.success
    assert first.bundle_id == second.bundle_id != third.bundle_id
    return store, first, second, third


def _snapshot(store):
    return {
        path.relative_to(store.store_root): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in store.store_root.rglob("*") if path.is_file() and path.name != "store.lock"
    }


def _bytes(data):
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _hash(data):
    payload = {key: value for key, value in data.items() if key not in {"diagnosis_hash", "diagnosed_at"}}
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _content(report):
    return {key: value for key, value in report.to_dict().items() if key not in {"diagnosis_hash", "diagnosed_at"}}


def _break_artifacts(store, *copies):
    for copy in copies:
        data = json.loads(copy.manifest_path.read_text(encoding="utf-8"))
        (copy.manifest_path.parent / f"{data['artifact_ids'][0]}.json").unlink()


def test_diagnosis_hash_can_be_recomputed_from_published_report(imported):
    store, *_ = imported
    report = diagnose_full_store(store)
    assert report.diagnosis_hash == report.compute_hash() == _hash(report.to_dict())
    serialized = json.loads(_bytes(report.to_dict(include_observation=True)))
    assert serialized["diagnosed_at"] == report.diagnosed_at
    assert "diagnosed_at" not in report.to_dict()
    assert serialized["diagnosis_hash"] == _hash(serialized)
    serialized["healthy"] = False
    assert serialized["diagnosis_hash"] != _hash(serialized)


def test_diagnosis_hash_tracks_real_corruption_and_verified_restoration(imported):
    store, _, second, _ = imported
    initial = diagnose_full_store(store)
    manifest = json.loads(second.manifest_path.read_text(encoding="utf-8"))
    artifact = second.manifest_path.parent / f"{manifest['artifact_ids'][0]}.json"
    saved = artifact.read_bytes()
    artifact.unlink()
    broken = diagnose_full_store(store)
    assert not broken.healthy and broken.hard_dq_count > initial.hard_dq_count
    assert initial.diagnosis_hash != broken.diagnosis_hash
    artifact.write_bytes(saved)
    restored = diagnose_full_store(store)
    assert restored.healthy and restored.diagnosis_hash == initial.diagnosis_hash


@pytest.mark.parametrize("scope", ["bundle", "run", "full"])
def test_identical_diagnoses_at_different_times_have_identical_evidence(imported, monkeypatch, scope):
    import hate.store.doctor_types as doctor_types

    store, first, second, _ = imported
    _break_artifacts(store, second)
    before = _snapshot(store)

    class Clock(datetime):
        hour = 1

        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 9, 10, cls.hour, tzinfo=UTC)

    def diagnose():
        if scope == "bundle":
            return diagnose_bundle(store, first.bundle_id)
        return diagnose_run(store, "run-2") if scope == "run" else diagnose_full_store(store)

    monkeypatch.setattr(doctor_types, "datetime", Clock)
    original = diagnose()
    Clock.hour = 2
    repeated = diagnose()
    assert original.diagnosed_at != repeated.diagnosed_at
    assert _bytes(original.to_dict()) == _bytes(repeated.to_dict())
    assert original.diagnosis_hash == repeated.diagnosis_hash
    assert _snapshot(store) == before


def test_valid_index_row_reordering_does_not_renumber_findings(imported):
    store, _, second, third = imported
    _break_artifacts(store, second, third)
    original = diagnose_full_store(store)
    for index in store.index_manager._all_indexes():
        rows = index.index_path.read_text(encoding="utf-8").splitlines()
        index.index_path.write_text("".join(row + "\n" for row in reversed(rows)), encoding="utf-8")
    before = _snapshot(store)
    repeated = diagnose_full_store(store)
    assert _content(original) == _content(repeated)
    assert original.diagnosis_hash == repeated.diagnosis_hash
    assert _snapshot(store) == before


@pytest.mark.parametrize("scope", ["bundle", "run", "full", "unresolved"])
def test_diagnosis_paths_and_hash_survive_store_relocation(imported, tmp_path, scope):
    store, first, second, _ = imported
    _break_artifacts(store, second)
    relocated_root = tmp_path / "relocated"
    assert relocated_root.resolve().is_relative_to(tmp_path.resolve())
    shutil.copytree(store.store_root, relocated_root)
    relocated = LocalStore(relocated_root)

    def diagnose(target):
        if scope == "bundle":
            return diagnose_bundle(target, first.bundle_id)
        if scope == "unresolved":
            return diagnose_bundle(target, "bundle-0000000000000000")
        return diagnose_run(target, "run-2") if scope == "run" else diagnose_full_store(target)

    original, repeated = diagnose(store), diagnose(relocated)
    assert _content(original) == _content(repeated)
    assert original.diagnosis_hash == repeated.diagnosis_hash
    assert all(item["path"].startswith("<store>") for item in original.to_dict()["findings"] if item["path"])
    assert all(item.path.startswith(str(store.store_root)) for item in original.findings if item.path)
    replay = replay_bundle(store, first.bundle_id, run_id="run-1")
    assert build_store_replay_report(replay, doctor_report=original) == build_store_replay_report(replay, doctor_report=repeated)


@pytest.mark.parametrize("scope,expected", [
    ("bundle", "run-1"), ("alias", "run-2"), ("run", "run-1"), ("full", None),
    ("missing_bundle", "missing-run"), ("missing_run", "missing-run"),
])
def test_report_identifies_the_diagnosed_run_even_without_findings(imported, scope, expected):
    store, first, _, _ = imported
    if scope == "bundle":
        report = diagnose_bundle(store, first.bundle_id, run_id="run-1")
    elif scope == "alias":
        report = diagnose_bundle(store, first.bundle_id)
    elif scope == "missing_bundle":
        report = diagnose_bundle(store, first.bundle_id, run_id="missing-run")
    elif scope in {"run", "missing_run"}:
        report = diagnose_run(store, expected)
    else:
        report = diagnose_full_store(store)
    assert report.to_dict()["run_id"] == expected


@pytest.mark.parametrize("scope", ["bundle", "run"])
def test_another_runs_healthy_diagnosis_cannot_validate_this_copy(imported, scope):
    store, first, _, _ = imported
    replay = replay_bundle(store, first.bundle_id, run_id="run-1")
    diagnosis = diagnose_bundle(store, first.bundle_id) if scope == "bundle" else diagnose_run(store, "run-2")
    assert diagnosis.healthy
    report = build_store_replay_report(replay, doctor_report=diagnosis)
    assert report["readiness_effect"] == "hard_dq"
    assert any(item.get("issue") == "report_identity_mismatch" and item.get("field") == "run_id" for item in report["diagnostics"])
    matching = diagnose_bundle(store, first.bundle_id, run_id="run-1")
    assert build_store_replay_report(replay, doctor_report=matching)["readiness_effect"] == "pass"


@pytest.mark.parametrize("corruption", ["hash", "metadata", "filename"])
def test_single_bundle_doctor_checks_the_alias_it_used(imported, corruption):
    store, first, second, _ = imported
    index_path = store.index_manager.bundles_index.index_path
    rows = [json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines()]
    row = next(row for row in rows if row["key"] == first.bundle_id)
    if corruption == "hash":
        row["hash"] = "sha256:" + "0" * 64
    elif corruption == "metadata":
        row["metadata"]["run_id"] = "run-1"
    else:
        row["value"] = str(second.manifest_path.relative_to(store.store_root))
        row["hash"] = "sha256:" + hashlib.sha256(second.manifest_path.read_bytes()).hexdigest()
    index_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    before = _snapshot(store)
    report = diagnose_bundle(store, first.bundle_id)
    assert not report.healthy
    assert any(item.category == "index" for item in report.findings)
    assert diagnose_bundle(store, first.bundle_id, run_id="run-1").healthy
    assert _snapshot(store) == before


def test_bad_alias_does_not_hide_physical_copy_findings(imported):
    store, first, second, _ = imported
    _break_artifacts(store, second)
    index = store.index_manager.bundles_index
    rows = [json.loads(line) for line in index.index_path.read_text(encoding="utf-8").splitlines()]
    next(row for row in rows if row["key"] == first.bundle_id)["metadata"]["run_id"] = "run-1"
    index.index_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    report = diagnose_bundle(store, first.bundle_id)
    issues = {item.diagnostics.get("issue") for item in report.findings}
    assert {"missing_artifact", "invalid_bundle_reference"} <= issues


@pytest.mark.subprocess
def test_doctor_evidence_is_stable_between_processes(imported):
    store, _, second, third = imported
    _break_artifacts(store, second, third)
    script = """
import json, sys
from pathlib import Path
from hate.store import LocalStore
from hate.store.doctor import diagnose_full_store
print(json.dumps(diagnose_full_store(LocalStore(Path(sys.argv[1]))).to_dict(), ensure_ascii=False, separators=(',', ':')))
"""
    outputs = []
    for seed in ("17", "29"):
        result = subprocess.run(
            [sys.executable, "-B", "-c", script, str(store.store_root)],
            env={**os.environ, "PYTHONHASHSEED": seed, "PYTHONUTF8": "1"}, capture_output=True, check=True,
        )
        outputs.append(result.stdout)
    assert outputs[0] == outputs[1]
