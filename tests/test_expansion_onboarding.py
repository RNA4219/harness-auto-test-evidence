"""Tests for HATE-GAP-027 guided onboarding evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from hate.expansion.onboarding import build_onboarding_report, evaluate_onboarding_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "expansion" / "onboarding"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "onboarding-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "onboarding-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_canonical_gap_027_fixture_paths_exist() -> None:
    assert (FIXTURES / "golden-walkthrough" / "fixture.json").is_file()
    assert (FIXTURES / "parser-failure-tutorial" / "fixture.json").is_file()


def test_golden_walkthrough_fixture_passes() -> None:
    result = evaluate_onboarding_fixture(_fixture("golden-walkthrough"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "none"
    _assert_report_contract(result["report"])


def test_parser_failure_tutorial_fixture_holds() -> None:
    result = evaluate_onboarding_fixture(_fixture("parser-failure-tutorial"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "onboarding_parser_failure_tutorial_missing"
    assert result["readiness_effect"] == "hold"
    _assert_report_contract(result["report"])


def test_missing_sample_repo_holds() -> None:
    report = build_onboarding_report({
        "sample_repos": [],
        "walkthrough_step_count": 5,
        "tutorial_failure_contract": True,
        "support_handoff_contract": True,
        "expected_output_defined": True,
        "five_minute_path_valid": True,
        "versioned_sample_repo": True,
    })

    assert report["overall_status"] == "hold"
    assert "onboarding_sample_repo_missing" in _codes(report)


def test_insufficient_walkthrough_steps_holds() -> None:
    report = build_onboarding_report({
        "sample_repos": ["https://github.com/example/sample-repo"],
        "walkthrough_step_count": 3,
        "tutorial_failure_contract": True,
        "support_handoff_contract": True,
        "expected_output_defined": True,
        "five_minute_path_valid": True,
        "versioned_sample_repo": True,
    })

    assert report["overall_status"] == "hold"
    assert "onboarding_walkthrough_insufficient" in _codes(report)


def test_missing_support_handoff_holds() -> None:
    report = build_onboarding_report({
        "sample_repos": ["https://github.com/example/sample-repo"],
        "walkthrough_step_count": 5,
        "tutorial_failure_contract": True,
        "support_handoff_contract": False,
        "expected_output_defined": True,
        "five_minute_path_valid": True,
        "versioned_sample_repo": True,
    })

    assert report["overall_status"] == "hold"
    assert "onboarding_support_handoff_missing" in _codes(report)


def test_onboarding_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["onboarding-report"] == "schemas/HATE/v1/onboarding-report.schema.json"
