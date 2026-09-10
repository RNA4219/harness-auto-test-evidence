from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime

import pytest

from hate.schema_resources import read_schema, validate_schema_instance
from hate.store import LocalStore
from hate.store.compare import compare_bundles_direct
from hate.store.doctor import diagnose_bundle
from hate.store.replay import build_store_replay_report, replay_bundle


@pytest.fixture
def imported(tmp_path):
    source = tmp_path / "source.json"
    store = LocalStore(tmp_path / "store")
    hold = dict(status="none", reason="test", held_since="2026-09-10T00:00:00Z", authorized_by="test")
    results = []
    for run, outcome in (("baseline", "failed"), ("current", "passed")):
        source.write_text(json.dumps({"nodes": [{"id": f"test-{i}", "kind": "test_result", "status": outcome} for i in range(8)]}), encoding="utf-8")
        result = store.import_bundle(source, run, run, hold)
        assert result.success
        results.append(result)
    return store, results[0], results[1]


def _bytes(report):
    return json.dumps(report, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _external_hash(data, hash_field, observation_field):
    payload = {key: value for key, value in data.items() if key not in {hash_field, observation_field}}
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def test_real_replays_and_comparisons_are_stable_across_different_execution_times(imported, monkeypatch):
    import hate.store.compare as compare_module
    import hate.store.replay as replay_module

    store, baseline, current = imported

    class Clock(datetime):
        hour = 1

        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 9, 10, cls.hour, tzinfo=UTC)

    monkeypatch.setattr(replay_module, "datetime", Clock)
    monkeypatch.setattr(compare_module, "datetime", Clock)
    first_replay = replay_bundle(store, current.bundle_id, baseline_ref="run:baseline")
    first_comparison = compare_bundles_direct(store, current.bundle_id, baseline.bundle_id)
    Clock.hour = 2
    second_replay = replay_bundle(store, current.bundle_id, baseline_ref="run:baseline")
    second_comparison = compare_bundles_direct(store, current.bundle_id, baseline.bundle_id)
    assert first_replay.replayed_at != second_replay.replayed_at
    assert first_comparison.compared_at != second_comparison.compared_at
    assert _bytes(first_replay.to_dict()) == _bytes(second_replay.to_dict())
    assert _bytes(first_comparison.to_dict()) == _bytes(second_comparison.to_dict())
    assert _bytes(build_store_replay_report(first_replay, comparison_report=first_comparison)) == _bytes(build_store_replay_report(second_replay, comparison_report=second_comparison))
    assert first_replay.compute_hash() == first_replay.replay_hash == second_replay.replay_hash
    assert first_comparison.compute_hash() == first_comparison.comparison_hash == second_comparison.comparison_hash


def test_hashes_can_be_verified_from_serialized_output_with_observation_metadata(imported):
    store, baseline, current = imported
    replay = replay_bundle(store, current.bundle_id)
    comparison = compare_bundles_direct(store, current.bundle_id, baseline.bundle_id)
    for report, hash_field, observation in ((replay, "replay_hash", "replayed_at"), (comparison, "comparison_hash", "compared_at")):
        serialized = json.loads(_bytes(report.to_dict(include_observation=True)))
        assert serialized[observation]
        assert observation not in report.to_dict()
        assert serialized[hash_field] == _external_hash(serialized, hash_field, observation)
        serialized["run_id"] = "different-run"
        assert serialized[hash_field] != _external_hash(serialized, hash_field, observation)
    envelope = build_store_replay_report(replay, comparison_report=comparison, include_observation=True)
    assert envelope["replay_hash"] == _external_hash(envelope, "replay_hash", "replayed_at")
    assert not validate_schema_instance(envelope, read_schema("store-replay-report.schema.json"))


def test_builder_normalizes_legacy_timestamp_without_mutating_input(imported):
    store, _, current = imported
    raw = replay_bundle(store, current.bundle_id).to_dict(include_observation=True)
    before = _bytes(raw)
    canonical = build_store_replay_report(raw)
    observed = build_store_replay_report(raw, include_observation=True)
    assert "replayed_at" not in canonical
    assert observed["replayed_at"] == raw["replayed_at"]
    assert canonical["replay_hash"] == observed["replay_hash"]
    assert _bytes(raw) == before
    assert not validate_schema_instance(canonical, read_schema("store-replay-report.schema.json"))


def test_manifest_json_key_order_does_not_change_replay_identity(imported):
    store, _, current = imported
    before = replay_bundle(store, current.bundle_id).to_dict()
    data = json.loads(current.manifest_path.read_text(encoding="utf-8"))
    current.manifest_path.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
    assert replay_bundle(store, current.bundle_id).to_dict() == before


def test_failed_replay_with_doctor_findings_is_also_reproducible(imported):
    store, _, current = imported
    manifest = store.read_manifest("current")
    (current.manifest_path.parent / f"{manifest.artifact_ids[0]}.json").unlink()
    reports = [
        build_store_replay_report(replay_bundle(store, current.bundle_id), doctor_report=diagnose_bundle(store, current.bundle_id))
        for _ in range(2)
    ]
    assert reports[0]["readiness_effect"] == "hard_dq"
    assert reports[0]["corruption_findings"]
    assert _bytes(reports[0]) == _bytes(reports[1])


def test_broken_frozen_copy_keeps_replay_identity_after_store_relocation(imported, tmp_path):
    store, baseline, current = imported
    manifest = store.read_manifest("current")
    (current.manifest_path.parent / f"{manifest.artifact_ids[0]}.json").unlink()
    relocated_root = tmp_path / "relocated-store"
    assert relocated_root.resolve().is_relative_to(tmp_path.resolve())
    shutil.copytree(store.store_root, relocated_root)
    relocated = LocalStore(relocated_root)
    assert replay_bundle(store, current.bundle_id).to_dict() == replay_bundle(relocated, current.bundle_id).to_dict()
    assert compare_bundles_direct(store, current.bundle_id, baseline.bundle_id).to_dict() == compare_bundles_direct(relocated, current.bundle_id, baseline.bundle_id).to_dict()


@pytest.mark.subprocess
def test_report_bytes_are_identical_across_process_hash_seeds(imported):
    store, baseline, current = imported
    script = """
import json, sys
from pathlib import Path
from hate.store import LocalStore
from hate.store.replay import replay_bundle, build_store_replay_report
from hate.store.compare import compare_bundles_direct
store = LocalStore(Path(sys.argv[1]))
replay = replay_bundle(store, sys.argv[2], baseline_ref='run:baseline')
comparison = compare_bundles_direct(store, sys.argv[2], sys.argv[3])
print(json.dumps([replay.to_dict(), comparison.to_dict(), build_store_replay_report(replay, comparison_report=comparison)], ensure_ascii=False, separators=(',', ':')))
"""
    outputs = []
    for seed in ("17", "29"):
        result = subprocess.run(
            [sys.executable, "-B", "-c", script, str(store.store_root), current.bundle_id, baseline.bundle_id],
            env={**os.environ, "PYTHONHASHSEED": seed, "PYTHONUTF8": "1"}, capture_output=True, check=True,
        )
        outputs.append(result.stdout)
    assert outputs[0] == outputs[1]
