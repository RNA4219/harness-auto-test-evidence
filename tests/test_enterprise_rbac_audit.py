"""UAT tests for enterprise RBAC and audit projection."""

from __future__ import annotations

import json
from pathlib import Path

from hate.enterprise import build_audit_event, build_enterprise_control_report, evaluate_rbac, validate_audit_events


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "enterprise" / "rbac-audit"
SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "schemas"
    / "HATE"
    / "v1"
    / "enterprise-control-report.schema.json"
)


def load_fixture(name: str) -> dict:
    with (FIXTURE_ROOT / name / "fixture.json").open(encoding="utf-8") as f:
        return json.load(f)


def evaluate_fixture(fixture: dict) -> dict:
    payload = fixture["input"]
    return evaluate_rbac(
        actor=payload["actor"],
        request=payload["request"],
        source_refs=payload["source_refs"],
    ).to_dict()


def test_packet_fixture_paths_exist() -> None:
    for name in [
        "admin-access",
        "reviewer-manual-review",
        "viewer-safe-metadata",
        "export-denied-quarantine",
        "missing-audit-event",
        "unauthorized-admin-action",
    ]:
        assert (FIXTURE_ROOT / name / "fixture.json").exists()


def test_admin_access_is_allowed_and_audited() -> None:
    fixture = load_fixture("admin-access")
    decision = evaluate_fixture(fixture)
    event = build_audit_event(decision, fixture["input"]["timestamp"]).to_dict()

    assert decision["decision"] == fixture["expected"]["decision"]
    assert decision["reason"] == "role_permission_allowed"
    assert decision["verdict_mutated"] is False
    assert event["actor"] == decision["actor"]
    assert event["action"] == "configure_policy"
    assert event["sourceRefs"] == decision["sourceRefs"]
    assert validate_audit_events([event], [decision])["readiness_effect"] == "pass"


def test_reviewer_can_operate_manual_review_records() -> None:
    fixture = load_fixture("reviewer-manual-review")
    decision = evaluate_fixture(fixture)
    event = build_audit_event(decision, fixture["input"]["timestamp"]).to_dict()

    assert decision["decision"] == "allowed"
    assert decision["resource_type"] == "manual_review"
    assert decision["allowed_scope"] == "confidential"
    assert event["reason"] == decision["reason"]


def test_viewer_gets_safe_metadata_for_quarantined_artifact_only() -> None:
    fixture = load_fixture("viewer-safe-metadata")
    decision = evaluate_fixture(fixture)

    assert decision["decision"] == "allowed"
    assert decision["allowed_scope"] == "safe_metadata"
    assert decision["reason"] == "quarantined_artifact_safe_metadata_only"
    assert decision["resource"]["quarantine_status"] == "quarantined"


def test_raw_quarantined_export_is_denied() -> None:
    fixture = load_fixture("export-denied-quarantine")
    decision = evaluate_fixture(fixture)

    assert decision["decision"] == "denied"
    assert decision["reason"] == "unsafe_export_scope_denied"
    assert decision["readiness_effect"] == "pass"
    assert decision["verdict_mutated"] is False


def test_missing_audit_event_holds_enterprise_report() -> None:
    fixture = load_fixture("missing-audit-event")
    decision = evaluate_fixture(fixture)
    report = build_enterprise_control_report([decision], [], decision["sourceRefs"])

    assert report["summary"]["readiness_effect"] == "hold"
    assert report["findings"][0]["code"] == "missing_audit_event"
    assert report["summary"]["rbac_decision_count"] == 1
    assert report["summary"]["audit_event_count"] == 0


def test_unauthorized_admin_action_is_denied_and_auditable() -> None:
    fixture = load_fixture("unauthorized-admin-action")
    decision = evaluate_fixture(fixture)
    event = build_audit_event(decision, fixture["input"]["timestamp"]).to_dict()

    assert decision["decision"] == "denied"
    assert decision["reason"] == "admin_permission_required"
    assert event["decision"] == "denied"
    assert validate_audit_events([event], [decision])["readiness_effect"] == "pass"


def test_hash_chain_break_is_detected() -> None:
    fixture = load_fixture("admin-access")
    decision = evaluate_fixture(fixture)
    event = build_audit_event(decision, fixture["input"]["timestamp"]).to_dict()
    event["reason"] = "tampered"

    validation = validate_audit_events([event], [decision])

    assert validation["readiness_effect"] == "hold"
    assert {finding["code"] for finding in validation["findings"]} == {
        "audit_hash_chain_broken",
        "missing_audit_event",
    }


def test_enterprise_control_schema_defines_rbac_and_audit_sections() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert "rbac_decisions" in schema["properties"]
    assert "audit_events" in schema["properties"]
    assert "enterprise_rbac_decision" in schema["$defs"]
    assert "enterprise_audit_event" in schema["$defs"]
    assert "verdict_mutated" in schema["$defs"]["enterprise_rbac_decision"]["properties"]
