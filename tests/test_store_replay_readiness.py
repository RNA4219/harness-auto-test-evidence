from __future__ import annotations

import pytest

from hate.schema_resources import read_schema, validate_schema_instance
from hate.store.replay import BaselineInfo, ReplayReport, build_store_replay_report


@pytest.mark.parametrize("field", ["integrity_ok", "legal_hold_preserved", "baseline_valid"])
def test_replay_failure_flags_are_not_lost_without_other_reports(field):
    replay = ReplayReport("bundle-current", "run-1", **{field: False})
    assert build_store_replay_report(replay)["readiness_effect"] == "hard_dq"


@pytest.mark.parametrize("report_field", ["doctor_report", "comparison_report", "migration_report"])
def test_individual_hard_findings_survive_stale_summary_counters(report_field):
    payload = {"findings": [{"severity": "hard_dq", "message": "test"}]}
    result = build_store_replay_report(ReplayReport("bundle-current", "run-1"), **{report_field: payload})
    assert result["readiness_effect"] == "hard_dq"


@pytest.mark.parametrize("payload,expected", [
    ({"compatibility_class": "compatible", "readiness_effect": "hard_dq"}, "hard_dq"),
    ({"compatibility_class": "incompatible"}, "hold"),
    ({"compatibility_class": "unknown"}, "hold"),
    ({"compatibility_class": "compatible"}, "pass"),
])
def test_migration_compatibility_and_severity_are_preserved(payload, expected):
    result = build_store_replay_report(ReplayReport("bundle-current", "run-1"), migration_report=payload)
    assert result["readiness_effect"] == expected
    assert result["migration_status"]["schema_compatible"] == (payload["compatibility_class"] == "compatible")


def test_compatible_migration_does_not_override_incompatible_replay_schema():
    result = build_store_replay_report(
        ReplayReport("bundle-current", "run-1", schema_compatible=False),
        migration_report={"compatibility_class": "compatible"},
    )
    assert result["readiness_effect"] == "hold"
    assert result["migration_status"]["schema_compatible"] is False


def test_empty_baseline_identity_is_not_validated_by_selection_method_alone():
    baseline = BaselineInfo("", "", "", "explicit_ref", False)
    result = build_store_replay_report(ReplayReport("bundle-current", "run-1"), baseline_info=baseline)
    assert result["baseline_resolution"]["valid"] is False
    assert result["readiness_effect"] == "hard_dq"


def test_legacy_report_without_integrity_field_remains_schema_readable():
    report = build_store_replay_report(ReplayReport("bundle-current", "run-1"))
    report.pop("integrity_ok")
    assert not validate_schema_instance(report, read_schema("store-replay-report.schema.json"))


@pytest.mark.parametrize("report_field", ["doctor_report", "comparison_report"])
def test_malformed_optional_report_is_not_silently_discarded(report_field):
    with pytest.raises(TypeError):
        build_store_replay_report(ReplayReport("bundle-current", "run-1"), **{report_field: []})


@pytest.mark.parametrize("field,value", [("bundle_id", "different-bundle"), ("run_id", "different-run")])
def test_other_targets_comparison_report_cannot_support_replay(field, value):
    comparison = {"bundle_id": "bundle-current", "run_id": "run-1", "baseline_bundle_id": "bundle-base", field: value}
    report = build_store_replay_report(ReplayReport("bundle-current", "run-1"), comparison_report=comparison)
    assert report["readiness_effect"] == "hard_dq"
    assert any(item["issue"] == "report_identity_mismatch" for item in report["diagnostics"])


@pytest.mark.parametrize("field,value", [("baseline_bundle_id", "different-bundle"), ("baseline_run_id", "different-run")])
def test_conflicting_baseline_evidence_is_not_overwritten(field, value):
    original = {"baseline_bundle_id": "bundle-base", "baseline_run_id": "base-run", "valid": True}
    replay = ReplayReport("bundle-current", "run-1", baseline_resolution=original)
    report = build_store_replay_report(replay, baseline_info={**original, field: value})
    assert report["baseline_resolution"]["valid"] is False
    assert report["readiness_effect"] == "hard_dq"
    assert replay.baseline_resolution == original
