"""Focused tests for HATE-GAP-046 security procurement report."""

from __future__ import annotations

import json
from pathlib import Path

from hate.expansion.portfolio_readiness import (
    build_security_procurement_report,
    evaluate_security_procurement_fixture,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "expansion" / "security-procurement"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "security-procurement-report.schema.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "security-procurement-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    assert "procurement_diagnostics" in report
    assert {
        "duplicate_control_claims",
        "claims_missing_evidence",
        "stale_control_claims",
        "claims_missing_reviewer_decision",
        "vulnerability_slas_missing_owner_due",
        "export_manifest_missing",
        "unsafe_export_detected",
        "review_decisions_without_source_ref",
    } <= set(report["procurement_diagnostics"])


def test_security_procurement_positive_fixture_has_procurement_diagnostics() -> None:
    result = evaluate_security_procurement_fixture(_fixture("trust-packet-safe"))
    report = result["report"]

    assert result["status"] == "pass"
    assert report["procurement_diagnostics"]["claims_missing_evidence"] == []
    assert report["procurement_diagnostics"]["claims_missing_reviewer_decision"] == []
    assert report["procurement_diagnostics"]["export_manifest_missing"] is False
    assert report["summary"]["review_decision_count"] == 1
    _assert_report_contract(report)


def test_security_procurement_control_evidence_reviewer_and_sla_hold() -> None:
    report = build_security_procurement_report({
        "security_review_packet": {
            "architecture": "local",
            "data_flow": "summary",
            "data_classes": "internal",
            "subprocessors": "none",
            "encryption": "host",
            "secrets_handling": "redacted",
            "retention_summary": "policy",
        },
        "control_claims": [
            {"claim_id": "control-dup", "claim_class": "implemented", "stale": True},
            {"claim_id": "control-dup", "claim_class": "implemented"},
        ],
        "vulnerability_slas": [{"sla_id": "critical", "severity": "critical", "overdue": True}],
        "review_decisions": [{"decision_id": "review-1", "target_ref": "other-control"}],
        "export_manifest": {},
        "procurement_export_safe": True,
    })

    codes = _codes(report)
    assert "security_procurement_duplicate_control_claim" in codes
    assert "security_procurement_control_evidence_missing" in codes
    assert "security_procurement_stale_control_claim" in codes
    assert "security_procurement_reviewer_missing" in codes
    assert "security_procurement_vulnerability_sla_incomplete" in codes
    assert "security_procurement_export_manifest_missing" in codes
    assert "security_procurement_overdue_critical_vulnerability" in codes
    _assert_report_contract(report)


def test_security_procurement_restricted_export_is_denied() -> None:
    report = build_security_procurement_report({
        "security_review_packet": {
            "architecture": "local",
            "data_flow": "summary",
            "data_classes": "internal",
            "subprocessors": "none",
            "encryption": "host",
            "secrets_handling": "redacted",
            "retention_summary": "policy",
        },
        "control_claims": [{"claim_id": "control", "claim_class": "implemented", "evidence_refs": ["e"], "sourceRef": "c"}],
        "vulnerability_slas": [{"sla_id": "medium", "severity": "medium", "owner": "sec", "due_date": "2026-07-30", "sourceRef": "sla"}],
        "review_decisions": [{"decision_id": "review", "target_ref": "control", "reviewer": "sec", "decision": "accepted", "sourceRef": "review"}],
        "export_manifest": {
            "manifest_id": "export",
            "redaction_profile": "safe",
            "approved_evidence_refs": ["e"],
            "contains_raw_artifacts": True,
            "contains_restricted_data": True,
        },
        "procurement_export_safe": True,
        "raw_artifact_in_export": False,
        "restricted_data_in_export": True,
    })

    assert "security_procurement_raw_artifact_export_denied" in _codes(report)
    assert report["procurement_diagnostics"]["unsafe_export_detected"] is True
