"""Tests for HATE-GAP-039 cost governance evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from hate.expansion.cost_governance import build_cost_governance_report, evaluate_cost_governance_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "expansion" / "cost-governance"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "cost-governance-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "cost-governance-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_canonical_gap_039_fixture_paths_exist() -> None:
    assert (FIXTURES / "forecast-within-budget" / "fixture.json").is_file()
    assert (FIXTURES / "egress-risk-hold" / "fixture.json").is_file()


def test_forecast_within_budget_fixture_passes() -> None:
    result = evaluate_cost_governance_fixture(_fixture("forecast-within-budget"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "none"
    _assert_report_contract(result["report"])


def test_egress_risk_hold_fixture_holds() -> None:
    result = evaluate_cost_governance_fixture(_fixture("egress-risk-hold"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "cost_governance_egress_risk_hold"
    assert result["readiness_effect"] == "hold"
    _assert_report_contract(result["report"])


def test_missing_tenant_scope_holds() -> None:
    report = build_cost_governance_report({
        "tenant_id": "",
        "forecast_window_days": 30,
        "storage_gb_current": 100.0,
        "storage_gb_forecast": 150.0,
        "storage_budget_gb": 200.0,
        "egress_gb_forecast": 50.0,
        "egress_budget_gb": 100.0,
        "retention_cost_forecast": 0.0,
        "budget_thresholds_defined": True,
        "storage_class_recommendation": "standard",
        "remediation_plan_defined": True,
    })

    assert report["overall_status"] == "hold"
    assert "cost_governance_missing_tenant_scope" in _codes(report)


def test_missing_budget_thresholds_holds() -> None:
    report = build_cost_governance_report({
        "tenant_id": "tenant-001",
        "forecast_window_days": 30,
        "storage_gb_current": 100.0,
        "storage_gb_forecast": 150.0,
        "storage_budget_gb": 200.0,
        "egress_gb_forecast": 50.0,
        "egress_budget_gb": 100.0,
        "retention_cost_forecast": 0.0,
        "budget_thresholds_defined": False,
        "storage_class_recommendation": "standard",
        "remediation_plan_defined": True,
    })

    assert report["overall_status"] == "hold"
    assert "cost_governance_budget_thresholds_missing" in _codes(report)


def test_storage_budget_exceeded_holds() -> None:
    report = build_cost_governance_report({
        "tenant_id": "tenant-001",
        "forecast_window_days": 30,
        "storage_gb_current": 100.0,
        "storage_gb_forecast": 300.0,
        "storage_budget_gb": 200.0,
        "egress_gb_forecast": 50.0,
        "egress_budget_gb": 100.0,
        "retention_cost_forecast": 0.0,
        "budget_thresholds_defined": True,
        "storage_class_recommendation": "standard",
        "remediation_plan_defined": True,
    })

    assert report["overall_status"] == "hold"
    assert "cost_governance_storage_budget_exceeded" in _codes(report)


def test_retention_cost_unbounded_holds() -> None:
    report = build_cost_governance_report({
        "tenant_id": "tenant-001",
        "forecast_window_days": 30,
        "storage_gb_current": 100.0,
        "storage_gb_forecast": 150.0,
        "storage_budget_gb": 200.0,
        "egress_gb_forecast": 50.0,
        "egress_budget_gb": 100.0,
        "retention_cost_forecast": 500.0,
        "budget_thresholds_defined": True,
        "storage_class_recommendation": "standard",
        "remediation_plan_defined": False,
    })

    assert report["overall_status"] == "hold"
    assert "cost_governance_retention_cost_unbounded" in _codes(report)


def test_missing_storage_class_recommendation_holds() -> None:
    report = build_cost_governance_report({
        "tenant_id": "tenant-001",
        "forecast_window_days": 30,
        "storage_gb_current": 100.0,
        "storage_gb_forecast": 150.0,
        "storage_budget_gb": 200.0,
        "egress_gb_forecast": 50.0,
        "egress_budget_gb": 100.0,
        "retention_cost_forecast": 0.0,
        "budget_thresholds_defined": True,
        "storage_class_recommendation": "",
        "remediation_plan_defined": True,
    })

    assert report["overall_status"] == "hold"
    assert "cost_governance_storage_recommendation_missing" in _codes(report)


def test_cost_governance_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["cost-governance-report"] == "schemas/HATE/v1/cost-governance-report.schema.json"