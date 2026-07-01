from __future__ import annotations

import json
from pathlib import Path

from hate.dashboard import build_dashboard_uat_report


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "dashboard-uat-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _passing_input() -> dict:
    checks = {
        check_id: {
            "status": "pass",
            "sourceRefs": [f"dashboard-uat:{check_id}"],
            "details": "verified",
        }
        for check_id in [
            "view_model_fixtures",
            "schema_validation",
            "redaction",
            "pagination",
            "source_ref_traceability",
        ]
    }
    return {
        "report_id": "dashboard-uat-report",
        "checks": checks,
        "state_report_refs": ["dashboard-state-report.json"],
        "manual_uat_refs": ["manual-bb-dashboard.md"],
        "view_model_results": [
            {
                "fixture_id": "ready-run",
                "view": "run_overview",
                "status": "pass",
                "sourceRefs": ["fixtures/dashboard/view-models/ready-run/fixture.json"],
            }
        ],
    }


def test_dashboard_uat_report_passes_with_required_checks() -> None:
    report = build_dashboard_uat_report(_passing_input(), source_refs=["UI_WORKFLOW_REQUIREMENTS.md"])

    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "dashboard-uat-report"
    assert report["status"] == "pass"
    assert report["readiness_effect"] == "none"
    assert report["findings"] == []
    assert "dashboard-state-report.json" in report["sourceRefs"]
    assert "UI_WORKFLOW_REQUIREMENTS.md" in report["sourceRefs"]


def test_dashboard_uat_blocks_not_run_required_check() -> None:
    data = _passing_input()
    data["checks"]["pagination"]["status"] = "not_run"

    report = build_dashboard_uat_report(data)

    assert report["status"] == "hold"
    assert report["readiness_effect"] == "hold"
    assert "dashboard_uat_required_check_not_run" in _codes(report)


def test_dashboard_uat_blocks_raw_unsafe_artifact_visibility() -> None:
    data = _passing_input()
    data["raw_unsafe_artifact_visible"] = True

    report = build_dashboard_uat_report(data)

    assert report["status"] == "hold"
    finding = next(item for item in report["findings"] if item["code"] == "dashboard_uat_unsafe_artifact_visible")
    assert finding["severity"] == "critical"


def test_dashboard_uat_blocks_product_ready_overclaim() -> None:
    data = _passing_input()
    data["product_ready_badge_with_missing_report"] = True

    report = build_dashboard_uat_report(data)

    assert report["status"] == "hold"
    assert "dashboard_uat_product_ready_overclaim" in _codes(report)


def test_dashboard_uat_schema_registered() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record for record in registry["records"]}

    assert schema["properties"]["record_type"]["const"] == "dashboard-uat-report"
    assert "dashboard-uat-report" in records
    assert records["dashboard-uat-report"]["schema"] == "schemas/HATE/v1/dashboard-uat-report.schema.json"
    assert records["dashboard-uat-report"]["unknown_field_policy"] == "warn"


def _codes(report: dict) -> set[str]:
    return {finding["code"] for finding in report["findings"]}
