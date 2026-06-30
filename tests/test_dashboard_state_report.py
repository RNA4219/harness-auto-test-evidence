"""Tests for HATE-GAP-008 dashboard state report."""

from __future__ import annotations

import json
from pathlib import Path

from hate.dashboard import build_dashboard_state_report, evaluate_dashboard_state_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "dashboard" / "view-states"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "dashboard-state-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "dashboard-state-report"
    assert report["status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    for state in report["view_states"]:
        assert set(schema["properties"]["view_states"]["items"]["required"]) <= set(state)
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_ready_dashboard_fixture_passes() -> None:
    result = evaluate_dashboard_state_fixture(_fixture("ready"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    report = result["report"]
    _assert_report_contract(report)
    assert report["view_states"][0]["view"] == "risk_graph"
    assert report["view_states"][0]["rbac"] == "allowed"


def test_rbac_denied_dashboard_fixture_is_hold() -> None:
    result = evaluate_dashboard_state_fixture(_fixture("rbac-denied"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "dashboard_rbac_denied_state_required"
    assert result["report"]["findings"][0]["severity"] == "high"


def test_required_view_missing_is_hold() -> None:
    report = build_dashboard_state_report({
        "required_views": ["run_overview", "risk_graph"],
        "view_states": [
            {
                "view": "run_overview",
                "state": "ready",
                "rbac": "allowed",
                "sourceRefs": ["product-readiness-report.json"],
                "required_actions": ["inspect_readiness"],
            }
        ],
    })

    assert report["status"] == "hold"
    assert "dashboard_required_view_missing" in _codes(report)


def test_source_refs_are_required() -> None:
    report = build_dashboard_state_report({
        "view_states": [
            {
                "view": "run_overview",
                "state": "ready",
                "rbac": "allowed",
                "sourceRefs": [],
                "visible_sourceRefs": False,
                "required_actions": ["inspect_readiness"],
            }
        ],
    })

    assert report["status"] == "hold"
    assert "dashboard_source_refs_missing" in _codes(report)


def test_empty_or_error_state_requires_action() -> None:
    report = build_dashboard_state_report({
        "view": "run_overview",
        "state": "empty",
        "rbac": "allowed",
        "sourceRefs": ["api-read-model.json"],
        "required_actions": [],
    })

    assert report["status"] == "hold"
    assert "dashboard_action_missing" in _codes(report)


def test_product_ready_badge_with_hard_dq_is_critical_hold() -> None:
    report = build_dashboard_state_report({
        "view": "run_overview",
        "state": "ready",
        "rbac": "allowed",
        "sourceRefs": ["product-readiness-report.json"],
        "required_actions": ["resolve_hard_dq"],
        "product_ready_badge": True,
        "hard_dq_count": 1,
    })

    assert report["status"] == "hold"
    finding = report["findings"][0]
    assert finding["code"] == "dashboard_product_ready_overclaim"
    assert finding["severity"] == "critical"


def test_restricted_content_or_secret_visible_is_critical_hold() -> None:
    report = build_dashboard_state_report({
        "view": "artifact_detail",
        "state": "quarantined",
        "rbac": "allowed",
        "sourceRefs": ["artifact-safety-report.json"],
        "restricted_path_visible": True,
    })

    assert report["status"] == "hold"
    assert report["findings"][0]["code"] == "dashboard_restricted_content_visible"
    assert report["findings"][0]["severity"] == "critical"


def test_severity_cannot_be_color_only() -> None:
    report = build_dashboard_state_report({
        "view": "risk_coverage",
        "state": "partial",
        "rbac": "allowed",
        "sourceRefs": ["risk-coverage-matrix.json"],
        "severity_color_only": True,
    })

    assert report["status"] == "hold"
    assert "dashboard_severity_color_only" in _codes(report)


def test_report_includes_required_views_states_and_source_refs() -> None:
    report = build_dashboard_state_report(
        {"view": "risk_graph", "state": "ready", "rbac": "allowed", "sourceRefs": ["dashboard-fixture.json"]},
        source_refs=["ui-workflow-requirements.md"],
    )

    _assert_report_contract(report)
    assert "risk_graph" in report["required_views"]
    assert "unauthorized" in report["required_states"]
    assert "dashboard-fixture.json" in report["sourceRefs"]
    assert "ui-workflow-requirements.md" in report["sourceRefs"]


def test_dashboard_state_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["dashboard-state-report"] == "schemas/HATE/v1/dashboard-state-report.schema.json"
