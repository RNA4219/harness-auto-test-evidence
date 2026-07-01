from __future__ import annotations

import json
from pathlib import Path

import pytest

from hate.profile import build_profile_report


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("profile", "expected_chain", "expected_policy"),
    [
        ("default", ["default"], "p0a_hard_dq_only"),
        ("strict", ["default", "strict"], "high_risk_missing_execution_and_unsafe_required_artifact_hard"),
        (
            "release",
            ["default", "strict", "release"],
            "strict_plus_unresolved_high_critical_static_and_open_manual_required_hard",
        ),
        ("experimental", ["default", "experimental"], "required_input_failures_only"),
    ],
)
def test_profile_report_publishes_effective_policy_table(
    profile: str,
    expected_chain: list[str],
    expected_policy: str,
) -> None:
    report = build_profile_report(profile, run_id="run-1", commit_sha="abc123")

    assert report["record_type"] == "profile_report"
    assert report["inherits"] == expected_chain
    assert report["effective_chain"] == expected_chain
    assert report["effective_rules"] == report["rules"]
    assert report["effective_policies"]["dq_policy"] == expected_policy
    assert set(report["effective_policies"]) == {
        "dq_policy",
        "soft_gap_policy",
        "aete_policy",
        "manual_policy",
        "export_policy",
    }
    assert set(report["policy_table"]) == {"default", "strict", "release", "experimental"}


def test_profile_report_drift_checks_cover_policy_completeness_and_qeg_boundary() -> None:
    report = build_profile_report("release")
    checks = {check["check_id"]: check for check in report["drift_checks"]}

    assert checks["profile-chain-known"]["status"] == "pass"
    assert checks["effective-rules-complete"]["status"] == "pass"
    assert checks["effective-policies-complete"]["status"] == "pass"
    assert checks["qeg-gate-boundary"]["status"] == "pass"
    assert checks["release-extends-strict"]["status"] == "pass"
    assert report["qeg_gate_policy"] is False
    assert report["release_gate_override"] is False
    assert report["publish_gate_override"] is False


def test_profile_report_schema_is_registered_and_shape_fixture_matches_contract() -> None:
    registry = json.loads((ROOT / "schemas/HATE/v1/schema-registry.json").read_text(encoding="utf-8"))
    profile_entries = [entry for entry in registry["records"] if entry["record_type"] == "profile_report"]

    assert len(profile_entries) == 1
    assert profile_entries[0]["schema"] == "schemas/HATE/v1/profile-report.schema.json"
    assert profile_entries[0]["phase"] == "P1a"
    assert profile_entries[0]["unknown_field_policy"] == "warn"
    assert profile_entries[0]["deprecated_fields"] == []
    assert (ROOT / profile_entries[0]["schema"]).exists()

    shape = json.loads(
        (ROOT / "fixtures/profile/inheritance/expected/profile-report.shape.json").read_text(encoding="utf-8")
    )
    report = build_profile_report("strict")
    for field in shape["required_fields"]:
        assert field in report
    assert set(shape["required_drift_checks"]).issubset({check["check_id"] for check in report["drift_checks"]})
