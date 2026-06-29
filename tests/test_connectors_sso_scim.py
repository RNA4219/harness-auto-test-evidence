"""UAT tests for SSO/SCIM dry-run connectors."""

from __future__ import annotations

import json
from pathlib import Path

from hate.connectors import (
    build_enterprise_connector_report,
    build_identity_connector_report,
    build_scim_diff,
    build_sso_mapping,
)


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "connectors" / "sso-scim"
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


def test_packet_fixture_paths_exist() -> None:
    for name in [
        "sso-valid-mapping",
        "scim-valid-diff",
        "group-role-sync",
        "missing-claim-mapping",
        "unsupported-claim",
        "live-network-attempt",
    ]:
        assert (FIXTURE_ROOT / name / "fixture.json").exists()


def test_sso_valid_mapping_dry_run() -> None:
    fixture = load_fixture("sso-valid-mapping")
    result = build_sso_mapping(
        fixture["input"]["enterprise_control_report"],
        fixture["input"]["mapping_config"],
    ).to_dict()

    expected = fixture["expected"]
    assert result["status"] == expected["status"]
    assert result["readiness_effect"] == expected["readiness_effect"]
    assert result["manual_review_required"] is expected["manual_review_required"]
    assert result["mapped_claims"] == expected["mapped_claims"]
    assert result["simulated_actions"]
    assert result["denied_actions"] == []


def test_scim_valid_diff_previews_actions_only() -> None:
    fixture = load_fixture("scim-valid-diff")
    result = build_scim_diff(
        fixture["input"]["enterprise_control_report"],
        fixture["input"]["connector_config"],
    ).to_dict()

    expected = fixture["expected"]
    assert result["status"] == expected["status"]
    assert len(result["simulated_actions"]) == expected["simulated_action_count"]
    assert len(result["denied_actions"]) == expected["denied_action_count"]
    assert result["readiness_effect"] == expected["readiness_effect"]
    assert {a["action"] for a in result["simulated_actions"]} == {"create_user", "create_group"}


def test_group_role_sync_preserves_audit_refs() -> None:
    fixture = load_fixture("group-role-sync")
    result = build_sso_mapping(
        fixture["input"]["enterprise_control_report"],
        fixture["input"]["mapping_config"],
    ).to_dict()

    expected = fixture["expected"]
    assert result["mapped_groups"] == expected["mapped_groups"]
    assert result["mapped_roles"] == expected["mapped_roles"]
    assert result["audit_event_refs"] == expected["audit_event_refs"]
    assert result["sourceRefs"] == fixture["input"]["enterprise_control_report"]["sourceRefs"]


def test_missing_claim_mapping_holds_for_manual_review() -> None:
    fixture = load_fixture("missing-claim-mapping")
    result = build_sso_mapping(
        fixture["input"]["enterprise_control_report"],
        fixture["input"]["mapping_config"],
    ).to_dict()

    expected = fixture["expected"]
    assert result["status"] == expected["status"]
    assert result["readiness_effect"] == expected["readiness_effect"]
    assert result["manual_review_required"] is expected["manual_review_required"]
    assert result["missing_claims"][0]["claim_name"] == expected["missing_claim"]


def test_unsupported_claim_holds_for_manual_review() -> None:
    fixture = load_fixture("unsupported-claim")
    result = build_sso_mapping(
        fixture["input"]["enterprise_control_report"],
        fixture["input"]["mapping_config"],
    ).to_dict()

    expected = fixture["expected"]
    assert result["status"] == expected["status"]
    assert result["readiness_effect"] == expected["readiness_effect"]
    assert result["manual_review_required"] is True
    assert result["unsupported_claims"][0]["claim_name"] == expected["unsupported_claim"]


def test_live_network_attempts_are_denied_and_redacted() -> None:
    fixture = load_fixture("live-network-attempt")
    report = fixture["input"]["enterprise_control_report"]

    sso_result = build_sso_mapping(report, fixture["input"]["mapping_config"]).to_dict()
    scim_result = build_scim_diff(report, fixture["input"]["connector_config"]).to_dict()

    assert sso_result["status"] == fixture["expected"]["sso_status"]
    assert scim_result["status"] == fixture["expected"]["scim_status"]
    assert sso_result["denied_actions"][0]["action"] == "live_network_validation"
    assert len(scim_result["denied_actions"]) == fixture["expected"]["denied_action_count"]
    assert {item["action"] for item in scim_result["denied_actions"]} == {
        "live_network_call",
        "delete_user",
    }

    serialized = json.dumps([sso_result, scim_result], sort_keys=True)
    for forbidden in fixture["expected"]["redacted_values"]:
        assert forbidden not in serialized


def test_disabled_connectors_are_non_gating() -> None:
    fixture = load_fixture("sso-valid-mapping")
    sso_result = build_sso_mapping(
        fixture["input"]["enterprise_control_report"],
        {**fixture["input"]["mapping_config"], "enabled": False},
    ).to_dict()
    scim_fixture = load_fixture("scim-valid-diff")
    scim_result = build_scim_diff(
        scim_fixture["input"]["enterprise_control_report"],
        {"enabled": False},
    ).to_dict()

    assert sso_result["status"] == "disabled"
    assert scim_result["status"] == "disabled"
    assert sso_result["readiness_effect"] == "pass"
    assert scim_result["readiness_effect"] == "pass"


def test_invalid_issuer_is_not_accepted() -> None:
    fixture = load_fixture("sso-valid-mapping")
    result = build_sso_mapping(
        fixture["input"]["enterprise_control_report"],
        {**fixture["input"]["mapping_config"], "issuer": "http://insecure.example.test"},
    ).to_dict()

    assert result["status"] == "invalid_config"
    assert result["configuration_status"] == "invalid"
    assert result["manual_review_required"] is True
    assert result["readiness_effect"] == "hold"


def test_enterprise_control_report_schema_defines_connector_dry_run_contract() -> None:
    fixture = load_fixture("sso-valid-mapping")
    sso_result = build_sso_mapping(
        fixture["input"]["enterprise_control_report"],
        fixture["input"]["mapping_config"],
    ).to_dict()
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    required = set(schema["$defs"]["connector_dry_run"]["required"])
    connector_record = {
        "connector_id": sso_result["mapping_id"],
        "mode": "sso",
        "enabled": sso_result["enabled"],
        "configuration_status": sso_result["configuration_status"],
        "simulated_actions": sso_result["simulated_actions"],
        "denied_actions": sso_result["denied_actions"],
        "redacted_diagnostics": sso_result["redacted_diagnostics"],
        "entitlement_status": "available",
        "readiness_effect": sso_result["readiness_effect"],
        "audit_event_refs": sso_result["audit_event_refs"],
        "sourceRefs": sso_result["sourceRefs"],
    }

    assert set(schema["required"]) == {
        "schema_version",
        "record_type",
        "connector_dry_runs",
        "sourceRefs",
    }
    assert required <= set(connector_record)
    assert "sso" in schema["$defs"]["connector_dry_run"]["properties"]["mode"]["enum"]
    assert "scim" in schema["$defs"]["connector_dry_run"]["properties"]["mode"]["enum"]


def test_p2p3_identity_connector_report_is_non_gating_and_safe() -> None:
    report = build_identity_connector_report("run-001", {"roles": ["auditor", "viewer"]})

    assert report["record_type"] == "identity_connector_report"
    assert {item["connector_id"] for item in report["connectors"]} == {"sso", "scim"}
    assert all(item["failure_policy"] == "non_gating_warning" for item in report["connectors"])
    assert all(item["canonical_bundle_mutated"] is False for item in report["connectors"])
    assert report["summary"]["non_gating_failure_count"] == 2
    assert report["safety"]["contains_connector_token"] is False
    assert report["precheck_decision_override"] is False


def test_p2p3_enterprise_connector_report_is_non_gating_and_safe() -> None:
    report = build_enterprise_connector_report("run-001")

    assert report["record_type"] == "enterprise_connector_report"
    assert {item["connector_id"] for item in report["connectors"]} == {
        "siem",
        "warehouse",
        "ticketing",
    }
    assert report["summary"]["failure_fixture_count"] == 3
    assert all(item["stable_warning_code"] == "HATE-EXP-001" for item in report["failure_fixtures"])
    assert report["payload_safety"]["connector_token_included"] is False
    assert report["qeg_verdict_override"] is False
