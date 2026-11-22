from __future__ import annotations

import json

import pytest

from hate.schema_resources import read_schema, validate_schema_instance
from hate.store import LocalStore, LocalStoreError
from hate.store.compare import compare_bundle_to_baseline
from hate.store.indexes import build_indexes_for_bundle
from hate.store.replay import build_store_replay_report, replay_bundle, select_baseline_by_timestamp


def _stamp(result, timestamp):
    data = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    data["created_at"] = timestamp
    assert not validate_schema_instance(data, read_schema("store-manifest.schema.json"))
    result.manifest_path.write_text(json.dumps(data), encoding="utf-8")
    return data


def _history(tmp_path, timestamps):
    store = LocalStore(tmp_path / "store")
    hold = dict(status="none", reason="test", held_since="2026-09-10T00:00:00Z", authorized_by="test")
    source = tmp_path / "source.json"
    results = []
    for number, timestamp in enumerate(timestamps):
        source.write_text(json.dumps({"sequence": number, "nodes": [{"kind": "test", "id": "one", "status": "passed"}]}), encoding="utf-8")
        result = store.import_bundle(source, "history", str(number), hold)
        assert result.success
        _stamp(result, timestamp)
        results.append(result)
    source.write_text('{"nodes": [{"kind": "test", "id": "one", "status": "failed"}]}', encoding="utf-8")
    probe = store.import_bundle(source, "probe", "probe", hold)
    assert probe.success
    return store, results, probe


def _files(store):
    return {
        path.relative_to(store.store_root): path.read_bytes()
        for path in store.store_root.rglob("*")
        if path.is_file() and path != store.store_root / "locks" / "store.lock"
    }


EQUAL_TIMES = [
    ("2026-09-10T01:00:00Z", "2026-09-10T01:00:00Z"),
    ("2026-09-10T01:00:00Z", "2026-09-10T10:00:00+09:00"),
    ("2026-09-10T01:00:00.1Z", "2026-09-10T01:00:00.100000000Z"),
]


@pytest.mark.parametrize("times", EQUAL_TIMES)
def test_equal_latest_instants_are_ambiguous_instead_of_sorted_by_bundle_id(tmp_path, times):
    store, history, _ = _history(tmp_path, ["2026-09-09T00:00:00Z", *times])
    before = _files(store)
    with pytest.raises(LocalStoreError) as caught:
        select_baseline_by_timestamp(store, "history")
    diagnostic = next(item for item in caught.value.diagnostics if item["issue"] == "ambiguous_baseline_timestamp")
    assert [item["bundle_id"] for item in diagnostic["candidates"]] == sorted(result.bundle_id for result in history[1:])
    assert _files(store) == before


def test_ambiguous_run_reference_preserves_candidate_evidence_in_reports(tmp_path):
    store, history, probe = _history(tmp_path, EQUAL_TIMES[1])
    before = _files(store)
    replay = replay_bundle(store, probe.bundle_id, baseline_ref="run:history")
    assert not replay.baseline_valid
    assert build_store_replay_report(replay)["readiness_effect"] == "hard_dq"
    comparison = compare_bundle_to_baseline(store, probe.bundle_id, baseline_ref="run:history")
    assert comparison.comparison_result.value == "incomparable" and comparison.baseline_bundle_id is None
    for report in (replay, comparison):
        candidate_evidence = [
            item for diagnostic in report.diagnostics for item in diagnostic.get("validation", [])
            if item["issue"] == "ambiguous_baseline_timestamp"
        ]
        assert len(candidate_evidence) == 1
        assert {item["bundle_id"] for item in candidate_evidence[0]["candidates"]} == {result.bundle_id for result in history}
    assert replay.to_dict() == replay_bundle(store, probe.bundle_id, baseline_ref="run:history").to_dict()
    assert _files(store) == before


def test_explicit_bundle_reference_resolves_timestamp_ambiguity(tmp_path):
    store, history, probe = _history(tmp_path, EQUAL_TIMES[0])
    reference = "bundle:" + history[0].bundle_id
    replay = replay_bundle(store, probe.bundle_id, baseline_ref=reference)
    comparison = compare_bundle_to_baseline(store, probe.bundle_id, baseline_ref=reference)
    assert replay.baseline_valid and replay.baseline_resolution["baseline_bundle_id"] == history[0].bundle_id
    assert comparison.baseline_bundle_id == history[0].bundle_id


def test_older_ties_do_not_prevent_selecting_a_unique_latest_candidate(tmp_path):
    store, history, _ = _history(tmp_path, [*EQUAL_TIMES[0], "2026-09-10T02:00:00Z"])
    assert select_baseline_by_timestamp(store, "history").baseline_bundle_id == history[-1].bundle_id


PRECISE_TIMES = [
    ("2026-09-10T01:00:00.123456200Z", "2026-09-10T01:00:00.123456100Z"),
    ("2026-09-10T01:00:00.123456" + "0" * 40 + "2Z", "2026-09-10T01:00:00.123456" + "0" * 40 + "1Z"),
    ("2026-09-10t10:00:00.123456200+09:00", "2026-09-10t01:00:00.123456100z"),
]


@pytest.mark.parametrize("later,earlier", PRECISE_TIMES)
@pytest.mark.parametrize("operation", ["baseline", "indexes"])
def test_fractional_seconds_are_not_truncated_when_choosing_latest(tmp_path, later, earlier, operation):
    store, history, _ = _history(tmp_path, EQUAL_TIMES[0])
    newer, older = sorted(history, key=lambda result: result.bundle_id)
    _stamp(newer, later)
    old_manifest = _stamp(older, earlier)
    if operation == "baseline":
        before = _files(store)
        assert select_baseline_by_timestamp(store, "history").baseline_bundle_id == newer.bundle_id
        assert _files(store) == before
    else:
        (store.store_root / "indexes" / "runs.jsonl").write_bytes(b"")
        evidence = {path: content for path, content in _files(store).items() if path.parts[0] == "runs"}
        build_indexes_for_bundle(store.store_root, older.manifest_path.parent, old_manifest)
        assert store.read_manifest("history").bundle_id == newer.bundle_id
        assert {path: content for path, content in _files(store).items() if path.parts[0] == "runs"} == evidence


@pytest.mark.parametrize("current_index", [0, 1, 2])
def test_implicit_comparison_uses_only_history_before_the_target(tmp_path, current_index):
    store, history, _ = _history(tmp_path, ["2026-09-10T01:00:00Z", "2026-09-10T02:00:00Z", "2026-09-10T03:00:00Z"])
    report = compare_bundle_to_baseline(store, history[current_index].bundle_id, run_id="history")
    if current_index:
        assert report.baseline_bundle_id == history[current_index - 1].bundle_id
    else:
        assert report.baseline_bundle_id is None and report.comparison_result.value == "incomparable"


@pytest.mark.parametrize("reference", [None, "run:history"])
def test_same_run_automatic_selection_excludes_same_time_and_future_copies(tmp_path, reference):
    store, history, _ = _history(tmp_path, ["2026-09-09T01:00:00Z", *EQUAL_TIMES[1], "2026-09-11T01:00:00Z"])
    report = compare_bundle_to_baseline(store, history[2].bundle_id, baseline_ref=reference, run_id="history")
    assert report.baseline_bundle_id == history[0].bundle_id


def test_explicit_bundle_comparison_can_select_a_later_copy(tmp_path):
    store, history, _ = _history(tmp_path, ["2026-09-10T01:00:00Z", "2026-09-10T02:00:00Z"])
    report = compare_bundle_to_baseline(store, history[0].bundle_id, baseline_ref="bundle:" + history[1].bundle_id, run_id="history")
    assert report.baseline_bundle_id == history[1].bundle_id


@pytest.mark.parametrize("operation", ["selection", "replay", "compare"])
def test_candidate_read_failure_is_not_silently_replaced_by_older_copy(tmp_path, monkeypatch, operation):
    store, history, probe = _history(tmp_path, ["2026-09-10T01:00:00Z", "2026-09-10T02:00:00Z"])
    read_manifest = store.read_manifest_by_bundle
    before = _files(store)

    def unavailable_candidate(bundle_id, *, run_id=None):
        if bundle_id == history[1].bundle_id:
            raise LocalStoreError("candidate became unreadable", "read_manifest", history[1].manifest_path, [
                {"issue": "candidate_read_failed", "path": str(history[1].manifest_path)},
            ])
        return read_manifest(bundle_id, run_id=run_id)

    monkeypatch.setattr(store, "read_manifest_by_bundle", unavailable_candidate)
    if operation == "selection":
        with pytest.raises(LocalStoreError):
            select_baseline_by_timestamp(store, "history")
    else:
        if operation == "replay":
            report = replay_bundle(store, probe.bundle_id, baseline_ref="run:history")
            assert not report.baseline_valid
        else:
            report = compare_bundle_to_baseline(store, probe.bundle_id, baseline_ref="run:history")
            assert report.comparison_result.value == "incomparable" and report.baseline_bundle_id is None
        assert any(item.get("issue") == "candidate_read_failed" for diagnostic in report.diagnostics for item in diagnostic.get("validation", []))
        assert all(item["path"].startswith("<store>/") for diagnostic in report.diagnostics for item in diagnostic.get("validation", []))
    assert _files(store) == before


@pytest.mark.parametrize("before", ["not-a-time", "2026-09-10T01:00:00"])
def test_invalid_time_bound_is_reported_without_falling_back_to_latest(tmp_path, before):
    store, _, _ = _history(tmp_path, ["2026-09-10T00:00:00Z"])
    files = _files(store)
    with pytest.raises(LocalStoreError) as caught:
        select_baseline_by_timestamp(store, "history", before_created_at=before)
    assert caught.value.diagnostics[0]["field"] == "before_created_at"
    assert _files(store) == files


def test_automatic_time_bound_keeps_submicrosecond_prior_candidate(tmp_path):
    later, earlier = PRECISE_TIMES[0]
    store, history, _ = _history(tmp_path, [earlier, later])
    report = compare_bundle_to_baseline(store, history[1].bundle_id, run_id="history")
    assert report.baseline_bundle_id == history[0].bundle_id
