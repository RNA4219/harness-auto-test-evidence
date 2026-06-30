"""Tests for HATE-GAP-012 real repository evaluation reports."""

from __future__ import annotations

import json
from pathlib import Path

from hate.evaluation import build_real_repo_evaluation_report, evaluate_real_repo_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "fixtures" / "evaluation" / "real-repo"
SCHEMA_PATH = ROOT / "schemas" / "HATE" / "v1" / "real-repo-evaluation-report.schema.json"
REGISTRY_PATH = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_ROOT / name / "fixture.json").read_text(encoding="utf-8"))


def test_contract_fixture_paths_exist() -> None:
    for name in ["baseline-pass", "regression-detected", "timeout-recorded", "subset-labeled"]:
        assert (FIXTURE_ROOT / name / "fixture.json").exists()


def test_baseline_pass_fixture_is_pass() -> None:
    fixture = load_fixture("baseline-pass")

    result = evaluate_real_repo_fixture(fixture)
    report = build_real_repo_evaluation_report(fixture["input"], fixture["fixture_id"])

    assert result["status"] == fixture["expected"]["status"]
    assert result["finding_code"] == ""
    assert report["overall_status"] == "pass"
    assert report["timeout_ms"] == 900000
    assert report["summary"]["regression_detected"] is False


def test_decision_downgrade_detects_regression() -> None:
    fixture = load_fixture("regression-detected")

    result = evaluate_real_repo_fixture(fixture)
    report = build_real_repo_evaluation_report(fixture["input"], fixture["fixture_id"])

    assert result["status"] == fixture["expected"]["status"]
    assert result["finding_code"] == fixture["expected"]["finding_code"]
    assert report["overall_status"] == "hold"
    assert report["findings"][0]["code"] == "real_repo_regression_detected"


def test_timeout_is_retained_as_hold_evidence() -> None:
    fixture = load_fixture("timeout-recorded")

    result = evaluate_real_repo_fixture(fixture)
    report = build_real_repo_evaluation_report(fixture["input"], fixture["fixture_id"])

    assert result["status"] == fixture["expected"]["status"]
    assert result["finding_code"] == fixture["expected"]["finding_code"]
    assert report["timeout_recorded"] is True
    assert report["summary"]["timeout_recorded"] is True


def test_subset_label_is_visible_and_does_not_prove_full_suite() -> None:
    fixture = load_fixture("subset-labeled")

    result = evaluate_real_repo_fixture(fixture)
    report = build_real_repo_evaluation_report(fixture["input"], fixture["fixture_id"])

    assert result["status"] == fixture["expected"]["status"]
    assert report["subset"]["is_subset"] is True
    assert report["subset"]["limitation_visible"] is True
    assert report["subset"]["proves_full_suite"] is False


def test_parser_failure_record_count_collapse_runtime_and_unsafe_artifact_hold() -> None:
    report = build_real_repo_evaluation_report({
        "repo_id": "stress-repo",
        "baseline_decision": "eligible",
        "current_decision": "eligible",
        "baseline_record_count": 100,
        "current_record_count": 10,
        "parser_status": "failed",
        "runtime_ms": 901000,
        "runtime_budget_ms": 900000,
        "unsafe_artifact_findings": 1,
    })

    codes = {finding["code"] for finding in report["findings"]}
    assert report["overall_status"] == "hold"
    assert "real_repo_parser_failure" in codes
    assert "real_repo_record_count_collapse" in codes
    assert "real_repo_runtime_budget_exceeded" in codes
    assert "real_repo_unsafe_artifact_finding" in codes


def test_unlabeled_subset_is_hold() -> None:
    report = build_real_repo_evaluation_report({
        "repo_id": "subset-repo",
        "baseline_decision": "eligible",
        "current_decision": "eligible",
        "subset": True,
    })

    assert report["overall_status"] == "hold"
    assert report["findings"][0]["code"] == "real_repo_subset_unlabeled"


def test_schema_and_registry_contract() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))

    assert schema["properties"]["record_type"]["const"] == "real-repo-evaluation-report"
    assert set(schema["required"]) >= {"repo_id", "baseline", "current", "timeout_recorded", "subset"}
    assert any(record["record_type"] == "real-repo-evaluation-report" for record in registry["records"])
