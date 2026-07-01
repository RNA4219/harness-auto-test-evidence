"""Tests for HATE-GAP-004 entitlement behavior."""

from __future__ import annotations

import json
from pathlib import Path

from hate.entitlement import evaluate_entitlement, evaluate_entitlement_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "entitlement"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "entitlement-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def test_team_ga_local_precheck_is_allowed() -> None:
    report = evaluate_entitlement_fixture(_fixture("team-ga-allowed"), source_version="test")

    assert report["record_type"] == "entitlement-report"
    assert report["status"] == "pass"
    assert report["plan"] == "team"
    assert report["feature"] == "local_precheck"
    assert report["entitlement_status"] == "available"
    assert report["precheck_decision_override"] is False
    assert report["qeg_verdict_override"] is False
    assert report["audit_events"][0]["decision"] == "allow"


def test_enterprise_feature_denied_for_team_plan() -> None:
    report = evaluate_entitlement_fixture(_fixture("enterprise-feature-denied"), source_version="test")

    assert report["status"] == "hold"
    assert report["finding_code"] == "entitlement_feature_denied"
    assert report["required_edition"] == "enterprise"
    assert report["entitlement_status"] == "denied"


def test_local_first_over_limit_is_non_gating_warning() -> None:
    report = evaluate_entitlement_fixture(_fixture("local-first-non-gating"), source_version="test")

    assert report["status"] == "pass"
    assert report["over_limit"] is True
    assert report["over_limit_action"] == "warn_only_preserve_evidence"
    assert report["entitlement_status"] == "over_limit_warning"
    assert report["findings"] == []


def test_precheck_override_is_blocked_even_when_feature_available() -> None:
    report = evaluate_entitlement_fixture(_fixture("precheck-override-denied"), source_version="test")

    assert report["status"] == "hold"
    assert report["finding_code"] == "entitlement_precheck_override_denied"
    assert report["precheck_decision_override"] is True
    assert report["audit_events"][0]["decision"] == "deny"


def test_qeg_verdict_override_is_blocked() -> None:
    report = evaluate_entitlement_fixture(_fixture("qeg-override-denied"), source_version="test")

    assert report["status"] == "hold"
    assert report["finding_code"] == "entitlement_qeg_override_denied"
    assert report["qeg_verdict_override"] is True


def test_usage_meter_over_limit_is_warning_not_hold() -> None:
    decision = evaluate_entitlement(
        {
            "plan": "team",
            "feature": "qeg_export",
            "mode": "ci",
            "usage": {"runs": 101},
            "limits": {"runs": 100},
        }
    )

    assert decision.status == "pass"
    assert decision.over_limit is True
    assert decision.over_limit_action == "warn_only_preserve_evidence"


def test_schema_registered_for_entitlement_report() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))

    assert schema["properties"]["record_type"]["const"] == "entitlement-report"
    assert "precheck_decision_override" in schema["required"]
    assert "qeg_verdict_override" in schema["required"]
    records = {record["record_type"]: record for record in registry["records"]}
    assert records["entitlement-report"]["schema"] == "schemas/HATE/v1/entitlement-report.schema.json"
    assert records["entitlement-report"]["phase"] == "P3"
    assert records["entitlement-report"]["unknown_field_policy"] == "warn"
