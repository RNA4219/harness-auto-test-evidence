"""Tests for HATE-GAP-057 historical regression evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from hate.analysis.historical_regression import (
    build_historical_regression_report,
    evaluate_historical_regression_fixture,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "expansion" / "historical-regression"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "historical-regression-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "historical-regression-report"
    assert report["overall_status"] in {"pass", "hold", "blocked"}
    assert report["readiness_effect"] in {"none", "hold", "blocked"}
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_canonical_gap_057_fixture_paths_exist() -> None:
    assert (FIXTURES / "stable-trend-pass" / "fixture.json").is_file()
    assert (FIXTURES / "recurring-failure-blocked" / "fixture.json").is_file()


def test_stable_trend_fixture_passes() -> None:
    result = evaluate_historical_regression_fixture(_fixture("stable-trend-pass"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "none"
    _assert_report_contract(result["report"])


def test_recurring_failure_fixture_holds() -> None:
    result = evaluate_historical_regression_fixture(_fixture("recurring-failure-blocked"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "historical_regression_recurring_failure_blocked"
    assert result["readiness_effect"] == "hold"
    _assert_report_contract(result["report"])


def test_parser_regression_detected_holds() -> None:
    report = build_historical_regression_report({
        "baseline_window": {"window_id": "w1", "start_date": "2024-01-01", "end_date": "2024-01-31", "baseline_metrics": {}},
        "trend_metrics": [],
        "recurrences": [],
        "parser_regression_detected": True,
        "recurring_failure_pattern": False,
        "risk_debt_burn_rate": 0.0,
        "analysis_scope": "test",
        "input_refs": [],
        "confidence": 0.9,
        "limits": {"max_trend_metrics": 50, "max_recurrences": 20, "risk_debt_threshold": 0.3, "confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "historical_regression_parser_regression_detected" in _codes(report)


def test_risk_debt_burn_rate_exceeds_threshold_holds() -> None:
    report = build_historical_regression_report({
        "baseline_window": {"window_id": "w1", "start_date": "2024-01-01", "end_date": "2024-01-31", "baseline_metrics": {}},
        "trend_metrics": [],
        "recurrences": [],
        "parser_regression_detected": False,
        "recurring_failure_pattern": False,
        "risk_debt_burn_rate": 0.5,
        "analysis_scope": "test",
        "input_refs": [],
        "confidence": 0.9,
        "limits": {"max_trend_metrics": 50, "max_recurrences": 20, "risk_debt_threshold": 0.3, "confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "historical_regression_risk_debt_burn_up" in _codes(report)


def test_recurrence_without_source_ref_holds() -> None:
    report = build_historical_regression_report({
        "baseline_window": {"window_id": "w1", "start_date": "2024-01-01", "end_date": "2024-01-31", "baseline_metrics": {}},
        "trend_metrics": [],
        "recurrences": [{"recurrence_id": "r1", "failure_pattern": "timeout", "occurrence_count": 2, "resolved": True, "severity": "low", "sourceRef": "", "rationale": ""}],
        "parser_regression_detected": False,
        "recurring_failure_pattern": False,
        "risk_debt_burn_rate": 0.0,
        "analysis_scope": "test",
        "input_refs": [],
        "confidence": 0.9,
        "limits": {"max_trend_metrics": 50, "max_recurrences": 20, "risk_debt_threshold": 0.3, "confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "historical_regression_recurring_failure_blocked" in _codes(report)


def test_confidence_below_threshold_holds() -> None:
    report = build_historical_regression_report({
        "baseline_window": {"window_id": "w1", "start_date": "2024-01-01", "end_date": "2024-01-31", "baseline_metrics": {}},
        "trend_metrics": [],
        "recurrences": [],
        "parser_regression_detected": False,
        "recurring_failure_pattern": False,
        "risk_debt_burn_rate": 0.0,
        "analysis_scope": "test",
        "input_refs": [],
        "confidence": 0.5,
        "limits": {"max_trend_metrics": 50, "max_recurrences": 20, "risk_debt_threshold": 0.3, "confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "historical_regression_recurring_failure_blocked" in _codes(report)


def test_historical_regression_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["historical-regression-report"] == "schemas/HATE/v1/historical-regression-report.schema.json"