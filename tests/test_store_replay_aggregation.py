from __future__ import annotations

import json

import pytest

from hate.schema_resources import read_schema, validate_schema_instance
from hate.store import LocalStore
from hate.store.compare import compare_bundles_direct
from hate.store.doctor import diagnose_bundle
from hate.store.replay import ReplayReport, build_store_replay_report, replay_bundle


def _copy(value):
    return json.loads(json.dumps(value))


def _base():
    return ReplayReport("bundle-current", "run-current")


def _comparison(result="regression"):
    return {
        "bundle_id": "bundle-current", "run_id": "run-current",
        "baseline_bundle_id": "bundle-base", "baseline_run_id": "run-base",
        "baseline_selection_method": "explicit_ref", "comparison_result": result,
        "artifact_diffs": [{"artifact_id": "test:one", "baseline_hash": "old", "current_hash": "new", "result": result, "details": {}}],
    }


@pytest.mark.parametrize("case", ["plain", "comparison", "doctor", "migration", "empty_diagnosis_failure"])
def test_published_envelope_survives_json_roundtrip_and_reaggregation(case):
    supplements = {}
    if case == "comparison":
        supplements["comparison_report"] = _comparison()
    elif case in {"doctor", "empty_diagnosis_failure"}:
        supplements["doctor_report"] = {
            "healthy": False, "hard_dq_count": 1,
            "findings": [{"finding_id": "F1", "severity": "hard_dq", "category": "artifact", "message": "missing"}]
            if case == "doctor" else [],
        }
    elif case == "migration":
        supplements["migration_report"] = {
            "compatibility_class": "incompatible", "readiness_effect": "hold",
            "checksum_before": "before", "checksum_after": "after", "rollback_plan_ref": "restore-plan",
        }
    original = build_store_replay_report(_base(), **supplements)
    saved = _copy(original)
    repeated = build_store_replay_report(saved)
    assert saved == original
    assert repeated == original
    assert build_store_replay_report(repeated) == repeated
    assert not validate_schema_instance(repeated, read_schema("store-replay-report.schema.json"))


@pytest.mark.parametrize("result", ["regression", "incomparable"])
def test_individual_comparison_failures_survive_stale_success_summary(result):
    comparison = _comparison(result)
    comparison["comparison_result"] = "no_change"
    report = build_store_replay_report(_base(), comparison_report=comparison)
    assert report["readiness_effect"] == "hold"


def test_positive_regression_counter_is_not_overridden_by_stale_success_summary():
    comparison = _comparison("no_change")
    comparison["regressions"] = 1
    report = build_store_replay_report(_base(), comparison_report=comparison)
    assert report["readiness_effect"] == "hold"


@pytest.mark.parametrize("source", ["comparison_report", "doctor_report", "migration_report"])
def test_supplemental_diagnostics_retain_the_reason_for_the_decision(source):
    diagnostic = {"issue": "unreadable_input", "severity": "hard_dq", "validation": [{"issue": "missing_record", "path": "<store>/record.json"}]}
    supplement = {"diagnostics": [diagnostic]}
    if source == "migration_report":
        supplement["compatibility_class"] = "compatible"
    original = _copy(supplement)
    report = build_store_replay_report(_base(), **{source: supplement})
    assert report["readiness_effect"] == "hard_dq"
    retained = [item for item in report["diagnostics"] if item.get("report") == source.removesuffix("_report")]
    assert any(item.get("detail") == diagnostic for item in retained)
    assert supplement == original
    assert build_store_replay_report(report) == report


def test_migration_finding_and_explicit_hold_flag_are_preserved():
    finding = {"code": "retention_pending", "severity": "warning", "message": "review retention"}
    migration = {"compatibility_class": "compatible", "migration_hold": True, "findings": [finding]}
    report = build_store_replay_report(_base(), migration_report=migration)
    assert report["readiness_effect"] == "hold"
    assert report["migration_status"]["migration_hold"]
    assert any(item.get("detail") == finding for item in report["diagnostics"])


def test_explicit_incompatible_migration_flag_is_not_overridden_by_compatible_label():
    migration = {"compatibility_class": "compatible", "schema_compatible": False}
    report = build_store_replay_report(_base(), migration_report=migration)
    assert report["readiness_effect"] == "hold"
    assert report["migration_status"]["schema_compatible"] is False


def test_doctor_target_and_structured_validation_are_kept_in_the_envelope(tmp_path):
    store = LocalStore(tmp_path / "store")
    source = tmp_path / "source.json"
    source.write_text('{"nodes": [{"id": "test:one", "kind": "test_result", "status": "pass"}]}', encoding="utf-8")
    hold = dict(status="none", reason="test", held_since="2026-09-10T00:00:00Z", authorized_by="test")
    result = store.import_bundle(source, "run-1", "revision", hold)
    assert result.success
    manifest = store.read_manifest("run-1")
    artifact = result.manifest_path.parent / f"{manifest.artifact_ids[0]}.json"
    artifact.write_text("{}", encoding="utf-8")
    diagnosis = diagnose_bundle(store, result.bundle_id, run_id="run-1")
    original = diagnosis.to_dict()
    replay = replay_bundle(store, result.bundle_id, run_id="run-1")
    report = build_store_replay_report(replay, doctor_report=diagnosis)
    for finding, retained in zip(original["findings"], report["corruption_findings"], strict=True):
        for field in ("bundle_id", "artifact_id", "expected", "actual", "diagnostics"):
            assert retained[field] == finding[field]
        assert retained["run_id"] == "run-1"
    assert diagnosis.to_dict() == original
    assert not validate_schema_instance(report, read_schema("store-replay-report.schema.json"))
    assert build_store_replay_report(_copy(report)) == report


def test_real_regression_remains_a_hold_after_saved_report_is_reopened(tmp_path):
    store = LocalStore(tmp_path / "store")
    source = tmp_path / "source.json"
    hold = dict(status="none", reason="test", held_since="2026-09-10T00:00:00Z", authorized_by="test")
    results = []
    for run, outcome in (("baseline", "passed"), ("current", "failed")):
        source.write_text(json.dumps({"nodes": [{"id": "test:one", "kind": "test_result", "status": outcome}]}), encoding="utf-8")
        result = store.import_bundle(source, run, "revision", hold)
        assert result.success
        results.append(result)
    baseline, current = results
    replay = replay_bundle(store, current.bundle_id, run_id="current")
    comparison = compare_bundles_direct(store, current.bundle_id, baseline.bundle_id)
    report = build_store_replay_report(replay, comparison_report=comparison)
    assert report["readiness_effect"] == "hold"
    assert build_store_replay_report(_copy(report)) == report


def test_reaggregation_with_new_supplements_does_not_erase_a_recorded_failure():
    report = build_store_replay_report(_base(), comparison_report=_comparison())
    revised = build_store_replay_report(report, comparison_report=_comparison("no_change"))
    assert revised["readiness_effect"] == "hold"
    assert build_store_replay_report(revised) == revised


@pytest.mark.parametrize("source", ["comparison_report", "migration_report"])
def test_reusing_the_same_supplement_does_not_duplicate_its_diagnostics(source):
    supplement = _comparison() if source == "comparison_report" else {"compatibility_class": "compatible", "readiness_effect": "hold"}
    supplement["diagnostics"] = [{"issue": "requires_review", "severity": "soft_dq"}]
    report = build_store_replay_report(_base(), **{source: supplement})
    repeated = build_store_replay_report(report, **{source: supplement})
    assert repeated == report


@pytest.mark.parametrize("prior_hold", ["migration", "recorded"])
def test_invalid_comparison_selection_takes_priority_over_existing_hold(prior_hold):
    comparison = _comparison("no_change")
    comparison["is_filename_sort_baseline"] = True
    replay = _base().to_dict()
    replay["baseline_resolution"] = {
        "baseline_bundle_id": "bundle-base", "baseline_run_id": "run-base", "baseline_created_at": "",
        "selection_method": "explicit_ref", "is_filename_sort": False, "valid": True,
    }
    if prior_hold == "migration":
        replay["schema_compatible"] = False
    else:
        replay["readiness_effect"] = "hold"
    assert build_store_replay_report(replay, comparison_report=comparison)["readiness_effect"] == "hard_dq"
