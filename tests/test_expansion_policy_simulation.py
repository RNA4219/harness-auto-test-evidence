"""Tests for HATE-GAP-028 policy simulation evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from hate.expansion.policy_simulation import build_policy_simulation_report, evaluate_policy_simulation_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "expansion" / "policy-simulation"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "policy-simulation-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "policy-simulation-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_canonical_gap_028_fixture_paths_exist() -> None:
    assert (FIXTURES / "safe-dry-run" / "fixture.json").is_file()
    assert (FIXTURES / "blast-radius-unbounded" / "fixture.json").is_file()


def test_safe_dry_run_fixture_passes() -> None:
    result = evaluate_policy_simulation_fixture(_fixture("safe-dry-run"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "none"
    _assert_report_contract(result["report"])


def test_blast_radius_unbounded_fixture_holds() -> None:
    result = evaluate_policy_simulation_fixture(_fixture("blast-radius-unbounded"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "policy_simulation_blast_radius_unbounded"
    assert result["readiness_effect"] == "hold"
    _assert_report_contract(result["report"])


def test_missing_dry_run_support_holds() -> None:
    report = build_policy_simulation_report({
        "dry_run_supported": False,
        "blast_radius_bounded": True,
        "rollback_plan_defined": True,
        "evidence_eligibility_impact_shown": True,
        "audit_evidence_generated": True,
        "affected_repos": ["repo-a"],
        "change_type": "policy-update",
        "max_affected_threshold": 5,
    })

    assert report["overall_status"] == "hold"
    assert "policy_simulation_dry_run_missing" in _codes(report)


def test_missing_rollback_plan_holds() -> None:
    report = build_policy_simulation_report({
        "dry_run_supported": True,
        "blast_radius_bounded": True,
        "rollback_plan_defined": False,
        "evidence_eligibility_impact_shown": True,
        "audit_evidence_generated": True,
        "affected_repos": ["repo-a"],
        "change_type": "policy-update",
        "max_affected_threshold": 5,
    })

    assert report["overall_status"] == "hold"
    assert "policy_simulation_rollback_missing" in _codes(report)


def test_missing_audit_evidence_holds() -> None:
    report = build_policy_simulation_report({
        "dry_run_supported": True,
        "blast_radius_bounded": True,
        "rollback_plan_defined": True,
        "evidence_eligibility_impact_shown": True,
        "audit_evidence_generated": False,
        "affected_repos": ["repo-a"],
        "change_type": "policy-update",
        "max_affected_threshold": 5,
    })

    assert report["overall_status"] == "hold"
    assert "policy_simulation_audit_evidence_missing" in _codes(report)


def test_policy_simulation_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["policy-simulation-report"] == "schemas/HATE/v1/policy-simulation-report.schema.json"
