"""Tests for platform dashboard wireframe conformance."""

from __future__ import annotations

import json
from pathlib import Path

from hate.p0a_schema import _validate_schema_value
from hate.dashboard import build_platform_dashboard_wireframe_report


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "platform" / "dashboard"
SCHEMAS = ROOT / "schemas" / "HATE" / "v1"


def test_platform_dashboard_wireframe_fixture_paths_exist() -> None:
    for name in [
        "portfolio-overview",
        "repo-regression-detail",
        "findings-owner-queue",
        "manual-review-blocking",
        "policy-drift",
        "artifact-unsafe-hidden",
        "degraded-large-query",
        "mobile-critical-summary",
    ]:
        assert (FIXTURES / name / "fixture.json").exists()


def test_portfolio_overview_health_and_trend_visible() -> None:
    fixture = _fixture("portfolio-overview")

    report = build_platform_dashboard_wireframe_report(fixture["input"], fixture["fixture_id"])
    view = report["view_inventory"][0]

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert view["view_id"] == "portfolio_overview"
    assert fixture["input"]["views"][0]["summary"]["open_holds"] == fixture["expected"]["open_holds"]
    assert fixture["input"]["views"][0]["summary"]["expired_debt"] == fixture["expected"]["expired_debt"]


def test_repo_regression_detail_exposes_score_breakdown() -> None:
    fixture = _fixture("repo-regression-detail")

    report = build_platform_dashboard_wireframe_report(fixture["input"], fixture["fixture_id"])

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert fixture["input"]["views"][0]["summary"]["regression_count"] == fixture["expected"]["regression_count"]
    assert "score_breakdown_visible" in report["visual_acceptance"]


def test_policy_drift_hash_diff_visible() -> None:
    fixture = _fixture("policy-drift")

    report = build_platform_dashboard_wireframe_report(fixture["input"], fixture["fixture_id"])

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert fixture["input"]["views"][0]["summary"]["changed_rules"] == fixture["expected"]["changed_rules"]
    assert report["view_inventory"][0]["sourceRefs"]
    assert report["view_inventory"][0]["sourceRefs"][0] in report["sourceRefs"]


def test_artifact_unsafe_body_is_hidden() -> None:
    fixture = _fixture("artifact-unsafe-hidden")

    report = build_platform_dashboard_wireframe_report(fixture["input"], fixture["fixture_id"])

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert "dashboard_wireframe_unsafe_body_rendered" not in _codes(report)
    assert report["state_matrix"][5]["state"] == "unsafe_hidden"


def test_degraded_large_query_state_is_visible() -> None:
    fixture = _fixture("degraded-large-query")

    report = build_platform_dashboard_wireframe_report(fixture["input"], fixture["fixture_id"])

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert report["view_inventory"][0]["state"] == fixture["expected"]["state"]
    assert "dashboard_wireframe_state_behavior_missing" not in _codes(report)


def test_mobile_critical_summary_preserves_decision_and_blocking_count() -> None:
    fixture = _fixture("mobile-critical-summary")

    report = build_platform_dashboard_wireframe_report(fixture["input"], fixture["fixture_id"])

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert fixture["input"]["views"][0]["summary"]["critical_visible"] is fixture["expected"]["critical_visible"]
    assert "mobile_critical_information_preserved" in report["visual_acceptance"]


def test_missing_required_view_holds() -> None:
    fixture = _fixture("portfolio-overview")
    fixture["input"]["required_views"] = ["portfolio_overview", "policy_drift"]

    report = build_platform_dashboard_wireframe_report(fixture["input"], "missing-policy-drift")

    assert report["overall_status"] == "hold"
    assert "dashboard_wireframe_required_view_missing" in _codes(report)


def test_unsafe_body_rendered_holds_even_in_detail_panel() -> None:
    fixture = _fixture("artifact-unsafe-hidden")
    fixture["input"]["views"][0]["selected_item"]["unsafe_artifact_body"] = "SECRET_SHOULD_NOT_RENDER"

    report = build_platform_dashboard_wireframe_report(fixture["input"], "unsafe-body-rendered")

    assert report["overall_status"] == "hold"
    assert "dashboard_wireframe_unsafe_body_rendered" in _codes(report)


def test_dashboard_wireframe_schema_registered() -> None:
    schema = json.loads((SCHEMAS / "platform-dashboard-wireframe-report.schema.json").read_text(encoding="utf-8"))
    registry = json.loads((SCHEMAS / "schema-registry.json").read_text(encoding="utf-8"))

    assert schema["properties"]["record_type"]["const"] == "platform-dashboard-wireframe-report"
    assert any(record["record_type"] == "platform-dashboard-wireframe-report" for record in registry["records"])


def test_dashboard_wireframe_report_matches_artifact_schema() -> None:
    fixture = _fixture("portfolio-overview")
    report = build_platform_dashboard_wireframe_report(fixture["input"], fixture["fixture_id"])
    schema = json.loads((SCHEMAS / "platform-dashboard-wireframe-report.schema.json").read_text(encoding="utf-8"))

    assert _validate_schema_value(report, schema, "$") == []


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> set[str]:
    return {finding["code"] for finding in report["findings"]}
