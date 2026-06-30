"""Tests for HATE-GAP-036 product analytics evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from hate.expansion.product_analytics import build_product_analytics_report, evaluate_product_analytics_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "expansion" / "product-analytics"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "product-analytics-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "product-analytics-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_canonical_gap_036_fixture_paths_exist() -> None:
    assert (FIXTURES / "aggregate-opt-in" / "fixture.json").is_file()
    assert (FIXTURES / "raw-path-event-denied" / "fixture.json").is_file()


def test_aggregate_opt_in_fixture_passes() -> None:
    result = evaluate_product_analytics_fixture(_fixture("aggregate-opt-in"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "none"
    _assert_report_contract(result["report"])


def test_raw_path_event_denied_fixture_holds() -> None:
    result = evaluate_product_analytics_fixture(_fixture("raw-path-event-denied"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "product_analytics_raw_path_event_denied"
    assert result["readiness_effect"] == "hold"
    _assert_report_contract(result["report"])


def test_missing_event_allowlist_holds() -> None:
    report = build_product_analytics_report({
        "event_allowlist_defined": False,
        "events": ["feature_usage"],
        "opt_in_required": True,
        "tenant_opt_in": True,
        "aggregate_only": True,
        "suppression_rules_defined": True,
        "usage_report_defined": True,
        "adoption_kpis": ["daily_active_users"],
        "raw_path_present": False,
        "raw_artifact_ref_present": False,
    })

    assert report["overall_status"] == "hold"
    assert "product_analytics_event_allowlist_missing" in _codes(report)


def test_missing_tenant_opt_in_holds() -> None:
    report = build_product_analytics_report({
        "event_allowlist_defined": True,
        "events": ["feature_usage"],
        "opt_in_required": True,
        "tenant_opt_in": False,
        "aggregate_only": True,
        "suppression_rules_defined": True,
        "usage_report_defined": True,
        "adoption_kpis": ["daily_active_users"],
        "raw_path_present": False,
        "raw_artifact_ref_present": False,
    })

    assert report["overall_status"] == "hold"
    assert "product_analytics_opt_in_missing" in _codes(report)


def test_missing_suppression_rules_holds() -> None:
    report = build_product_analytics_report({
        "event_allowlist_defined": True,
        "events": ["feature_usage"],
        "opt_in_required": True,
        "tenant_opt_in": True,
        "aggregate_only": True,
        "suppression_rules_defined": False,
        "usage_report_defined": True,
        "adoption_kpis": ["daily_active_users"],
        "raw_path_present": False,
        "raw_artifact_ref_present": False,
    })

    assert report["overall_status"] == "hold"
    assert "product_analytics_suppression_rules_missing" in _codes(report)


def test_missing_usage_report_holds() -> None:
    report = build_product_analytics_report({
        "event_allowlist_defined": True,
        "events": ["feature_usage"],
        "opt_in_required": True,
        "tenant_opt_in": True,
        "aggregate_only": True,
        "suppression_rules_defined": True,
        "usage_report_defined": False,
        "adoption_kpis": ["daily_active_users"],
        "raw_path_present": False,
        "raw_artifact_ref_present": False,
    })

    assert report["overall_status"] == "hold"
    assert "product_analytics_usage_report_missing" in _codes(report)


def test_missing_adoption_kpi_holds() -> None:
    report = build_product_analytics_report({
        "event_allowlist_defined": True,
        "events": ["feature_usage"],
        "opt_in_required": True,
        "tenant_opt_in": True,
        "aggregate_only": True,
        "suppression_rules_defined": True,
        "usage_report_defined": True,
        "adoption_kpis": [],
        "raw_path_present": False,
        "raw_artifact_ref_present": False,
    })

    assert report["overall_status"] == "hold"
    assert "product_analytics_adoption_kpi_missing" in _codes(report)


def test_raw_artifact_ref_denied_holds() -> None:
    report = build_product_analytics_report({
        "event_allowlist_defined": True,
        "events": ["feature_usage"],
        "opt_in_required": True,
        "tenant_opt_in": True,
        "aggregate_only": True,
        "suppression_rules_defined": True,
        "usage_report_defined": True,
        "adoption_kpis": ["daily_active_users"],
        "raw_path_present": False,
        "raw_artifact_ref_present": True,
    })

    assert report["overall_status"] == "hold"
    assert "product_analytics_raw_artifact_ref_denied" in _codes(report)


def test_product_analytics_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["product-analytics-report"] == "schemas/HATE/v1/product-analytics-report.schema.json"


def test_product_analytics_no_report_json_alias_schema() -> None:
    alias_path = ROOT / "schemas" / "HATE" / "v1" / "product-analytics-report.json"
    assert not alias_path.exists()