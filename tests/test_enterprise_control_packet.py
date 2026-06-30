"""Tests for HATE-GAP-015 enterprise control implementation packets."""

from __future__ import annotations

import json
from pathlib import Path

from hate.enterprise import build_enterprise_control_packet_report, evaluate_enterprise_control_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "enterprise" / "control"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "enterprise-control-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "enterprise-control-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    assert isinstance(report["rbac_decisions"], list)
    assert isinstance(report["audit_events"], list)
    assert isinstance(report["control_packets"], list)
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_canonical_gap_015_fixture_paths_exist() -> None:
    assert (FIXTURES / "admin-allowed" / "fixture.json").is_file()
    assert (FIXTURES / "auditor-write-denied" / "fixture.json").is_file()


def test_admin_update_retention_policy_passes() -> None:
    result = evaluate_enterprise_control_fixture(_fixture("admin-allowed"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "none"
    _assert_report_contract(result["report"])
    decision = result["report"]["rbac_decisions"][0]
    assert decision["decision"] == "allowed"
    assert decision["action"] == "configure_policy"
    assert result["report"]["audit_events"][0]["action"] == "configure_policy"


def test_auditor_update_retention_policy_is_denied() -> None:
    result = evaluate_enterprise_control_fixture(_fixture("auditor-write-denied"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "enterprise_auditor_write_denied"
    assert result["readiness_effect"] == "hold"
    _assert_report_contract(result["report"])
    assert result["report"]["rbac_decisions"][0]["decision"] == "denied"


def test_maintainer_admin_control_requires_admin() -> None:
    report = build_enterprise_control_packet_report({
        "role": "maintainer",
        "action": "update_retention_policy",
    })

    assert report["overall_status"] == "hold"
    assert "enterprise_admin_permission_required" in _codes(report)


def test_service_account_cannot_replace_human_approval() -> None:
    report = build_enterprise_control_packet_report({
        "role": "service_account",
        "action": "approve_review",
        "resource_type": "manual_review",
    })

    assert report["overall_status"] == "hold"
    assert "enterprise_service_account_human_approval_denied" in _codes(report)


def test_viewer_can_read_report_without_mutating_verdict() -> None:
    report = build_enterprise_control_packet_report({
        "role": "viewer",
        "action": "read",
        "resource_type": "report",
        "classification": "internal",
    })

    assert report["overall_status"] == "pass"
    assert report["rbac_decisions"][0]["verdict_mutated"] is False
    assert report["summary"]["readiness_effect"] == "pass"


def test_control_packets_accept_batch_input() -> None:
    report = build_enterprise_control_packet_report({
        "control_packets": [
            {"role": "admin", "action": "update_retention_policy"},
            {"role": "auditor", "action": "read", "resource_type": "audit", "classification": "internal"},
        ]
    })

    assert report["overall_status"] == "pass"
    assert report["summary"]["packet_count"] == 2
    assert report["summary"]["rbac_decision_count"] == 2


def test_enterprise_control_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["enterprise-control-report"] == "schemas/HATE/v1/enterprise-control-report.schema.json"
