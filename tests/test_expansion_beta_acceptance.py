"""Tests for HATE-GAP-040 beta acceptance evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from hate.expansion.beta_acceptance import build_beta_acceptance_report, evaluate_beta_acceptance_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "expansion" / "beta-acceptance"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "beta-acceptance-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "beta-acceptance-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_canonical_gap_040_fixture_paths_exist() -> None:
    assert (FIXTURES / "cohort-exit-pass" / "fixture.json").is_file()
    assert (FIXTURES / "blocker-feedback-hold" / "fixture.json").is_file()


def test_cohort_exit_pass_fixture_passes() -> None:
    result = evaluate_beta_acceptance_fixture(_fixture("cohort-exit-pass"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "none"
    _assert_report_contract(result["report"])


def test_blocker_feedback_hold_fixture_holds() -> None:
    result = evaluate_beta_acceptance_fixture(_fixture("blocker-feedback-hold"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "beta_acceptance_blocker_feedback_hold"
    assert result["readiness_effect"] == "hold"
    _assert_report_contract(result["report"])


def test_missing_cohort_holds() -> None:
    report = build_beta_acceptance_report({
        "cohort_defined": False,
        "cohort_id": "",
        "customer_evidence_limits_defined": True,
        "feedback_items": [],
        "blocker_count": 0,
        "critical_blocker_count": 0,
        "triage_owner": "triage-owner-001",
        "exit_criteria_defined": True,
        "exit_criteria_met": True,
        "acceptance_record_present": True,
        "customer_secret_present": False,
    })

    assert report["overall_status"] == "hold"
    assert "beta_acceptance_cohort_missing" in _codes(report)


def test_missing_customer_evidence_limits_holds() -> None:
    report = build_beta_acceptance_report({
        "cohort_defined": True,
        "cohort_id": "beta-cohort-001",
        "customer_evidence_limits_defined": False,
        "feedback_items": [],
        "blocker_count": 0,
        "critical_blocker_count": 0,
        "triage_owner": "triage-owner-001",
        "exit_criteria_defined": True,
        "exit_criteria_met": True,
        "acceptance_record_present": True,
        "customer_secret_present": False,
    })

    assert report["overall_status"] == "hold"
    assert "beta_acceptance_customer_evidence_limits_missing" in _codes(report)


def test_unclassified_feedback_holds() -> None:
    report = build_beta_acceptance_report({
        "cohort_defined": True,
        "cohort_id": "beta-cohort-001",
        "customer_evidence_limits_defined": True,
        "feedback_items": [
            {
                "feedback_id": "feedback-001",
                "classification": "",
                "severity": "low",
                "sourceRef": "feedback-001",
            }
        ],
        "blocker_count": 0,
        "critical_blocker_count": 0,
        "triage_owner": "triage-owner-001",
        "exit_criteria_defined": True,
        "exit_criteria_met": True,
        "acceptance_record_present": True,
        "customer_secret_present": False,
    })

    assert report["overall_status"] == "hold"
    assert "beta_acceptance_feedback_unclassified" in _codes(report)


def test_critical_blocker_present_holds() -> None:
    report = build_beta_acceptance_report({
        "cohort_defined": True,
        "cohort_id": "beta-cohort-001",
        "customer_evidence_limits_defined": True,
        "feedback_items": [],
        "blocker_count": 0,
        "critical_blocker_count": 1,
        "triage_owner": "triage-owner-001",
        "exit_criteria_defined": True,
        "exit_criteria_met": True,
        "acceptance_record_present": True,
        "customer_secret_present": False,
    })

    assert report["overall_status"] == "hold"
    assert "beta_acceptance_critical_blocker_present" in _codes(report)


def test_missing_triage_owner_holds() -> None:
    report = build_beta_acceptance_report({
        "cohort_defined": True,
        "cohort_id": "beta-cohort-001",
        "customer_evidence_limits_defined": True,
        "feedback_items": [],
        "blocker_count": 0,
        "critical_blocker_count": 0,
        "triage_owner": "",
        "exit_criteria_defined": True,
        "exit_criteria_met": True,
        "acceptance_record_present": True,
        "customer_secret_present": False,
    })

    assert report["overall_status"] == "hold"
    assert "beta_acceptance_triage_owner_missing" in _codes(report)


def test_missing_exit_criteria_holds() -> None:
    report = build_beta_acceptance_report({
        "cohort_defined": True,
        "cohort_id": "beta-cohort-001",
        "customer_evidence_limits_defined": True,
        "feedback_items": [],
        "blocker_count": 0,
        "critical_blocker_count": 0,
        "triage_owner": "triage-owner-001",
        "exit_criteria_defined": False,
        "exit_criteria_met": True,
        "acceptance_record_present": True,
        "customer_secret_present": False,
    })

    assert report["overall_status"] == "hold"
    assert "beta_acceptance_exit_criteria_missing" in _codes(report)


def test_exit_criteria_not_met_holds() -> None:
    report = build_beta_acceptance_report({
        "cohort_defined": True,
        "cohort_id": "beta-cohort-001",
        "customer_evidence_limits_defined": True,
        "feedback_items": [],
        "blocker_count": 0,
        "critical_blocker_count": 0,
        "triage_owner": "triage-owner-001",
        "exit_criteria_defined": True,
        "exit_criteria_met": False,
        "acceptance_record_present": True,
        "customer_secret_present": False,
    })

    assert report["overall_status"] == "hold"
    assert "beta_acceptance_exit_criteria_not_met" in _codes(report)


def test_customer_secret_denied_holds() -> None:
    report = build_beta_acceptance_report({
        "cohort_defined": True,
        "cohort_id": "beta-cohort-001",
        "customer_evidence_limits_defined": True,
        "feedback_items": [],
        "blocker_count": 0,
        "critical_blocker_count": 0,
        "triage_owner": "triage-owner-001",
        "exit_criteria_defined": True,
        "exit_criteria_met": True,
        "acceptance_record_present": True,
        "customer_secret_present": True,
    })

    assert report["overall_status"] == "hold"
    assert "beta_acceptance_customer_secret_denied" in _codes(report)


def test_beta_acceptance_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["beta-acceptance-report"] == "schemas/HATE/v1/beta-acceptance-report.schema.json"