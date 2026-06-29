"""UAT tests for ops (SIEM/warehouse/ticketing) dry-run connectors."""

from __future__ import annotations

import json
from pathlib import Path

from hate.connectors import (
    build_ops_connector,
    build_ops_connector_report,
)


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "connectors" / "ops"
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
        "siem-safe-event",
        "warehouse-safe-row",
        "ticket-safe-summary",
        "support-safe-bundle",
        "unsafe-artifact-export",
        "live-network-attempt",
        "siem-export",
        "warehouse-export",
        "ticketing-sync",
        "ops-failure-nongating",
    ]:
        assert (FIXTURE_ROOT / name / "fixture.json").exists()


def test_siem_export_dry_run_preview() -> None:
    fixture = load_fixture("siem-export")
    result = build_ops_connector(
        fixture["input"]["enterprise_control_report"],
        "siem",
        fixture["input"]["connector_config"],
    ).to_dict()

    expected = fixture["expected"]
    assert result["connector_id"] == expected["connector_id"]
    assert result["mode"] == expected["mode"]
    assert result["status"] == expected["status"]
    assert result["enabled"] == expected["enabled"]
    assert result["readiness_effect"] == expected["readiness_effect"]
    assert len(result["simulated_actions"]) == expected["simulated_actions_count"]
    assert result["denied_actions"] == []
    assert result["payload_kind"] == expected["payload_kind"]


def test_warehouse_export_dry_run_preview() -> None:
    fixture = load_fixture("warehouse-export")
    result = build_ops_connector(
        fixture["input"]["enterprise_control_report"],
        "warehouse",
        fixture["input"]["connector_config"],
    ).to_dict()

    expected = fixture["expected"]
    assert result["connector_id"] == expected["connector_id"]
    assert result["mode"] == expected["mode"]
    assert result["status"] == expected["status"]
    assert result["enabled"] == expected["enabled"]
    assert result["readiness_effect"] == expected["readiness_effect"]
    assert len(result["simulated_actions"]) == expected["simulated_actions_count"]
    assert result["denied_actions"] == []
    assert result["payload_kind"] == expected["payload_kind"]


def test_ticketing_sync_dry_run_preview() -> None:
    fixture = load_fixture("ticketing-sync")
    result = build_ops_connector(
        fixture["input"]["enterprise_control_report"],
        "ticketing",
        fixture["input"]["connector_config"],
    ).to_dict()

    expected = fixture["expected"]
    assert result["connector_id"] == expected["connector_id"]
    assert result["mode"] == expected["mode"]
    assert result["status"] == expected["status"]
    assert result["enabled"] == expected["enabled"]
    assert result["readiness_effect"] == expected["readiness_effect"]
    assert len(result["simulated_actions"]) == expected["simulated_actions_count"]
    assert result["denied_actions"] == []
    assert result["payload_kind"] == expected["payload_kind"]


def test_ops_failure_is_non_gating() -> None:
    fixture = load_fixture("ops-failure-nongating")
    report = build_ops_connector_report(
        fixture["input"]["enterprise_control_report"],
        fixture["input"]["connector_config"],
    )

    expected = fixture["expected"]
    assert set(c["connector_id"] for c in report["connectors"]) == set(expected["connectors"])
    assert all(c["readiness_effect"] == "non_gating_failure" for c in report["connectors"])
    assert report["boundaries"]["canonical_bundle_mutated"] is False
    assert report["boundaries"]["precheck_decision_override"] is False
    assert report["boundaries"]["qeg_verdict_override"] is False
    assert report["safety"]["contains_connector_token"] is False


def test_ops_live_network_attempts_denied() -> None:
    fixture = load_fixture("siem-export")
    result = build_ops_connector(
        fixture["input"]["enterprise_control_report"],
        "siem",
        {**fixture["input"]["connector_config"], "live_network_attempt": True},
    ).to_dict()

    assert result["status"] == "denied_action"
    assert result["readiness_effect"] == "hold"
    assert any(a["action"] == "live_network_call" for a in result["denied_actions"])


def test_ops_destructive_actions_denied() -> None:
    fixture = load_fixture("siem-export")
    report_with_destructive = {
        **fixture["input"]["enterprise_control_report"],
        "siem_export": {
            **fixture["input"]["enterprise_control_report"]["siem_export"],
            "requested_actions": [
                {"action": "purge_events", "target": "all"},
                {"action": "export_audit_events", "target": "recent"},
            ],
        },
    }
    result = build_ops_connector(report_with_destructive, "siem", fixture["input"]["connector_config"]).to_dict()

    assert result["status"] == "denied_action"
    assert any(a["action"] == "purge_events" for a in result["denied_actions"])
    assert any(a["action"] == "export_audit_events" for a in result["simulated_actions"])


def test_ops_disabled_connector_is_pass() -> None:
    fixture = load_fixture("siem-export")
    result = build_ops_connector(
        fixture["input"]["enterprise_control_report"],
        "siem",
        {**fixture["input"]["connector_config"], "enabled": False},
    ).to_dict()

    assert result["status"] == "disabled"
    assert result["enabled"] is False
    assert result["readiness_effect"] == "pass"


def test_ops_connector_schema_alignment() -> None:
    fixture = load_fixture("siem-export")
    result = build_ops_connector(
        fixture["input"]["enterprise_control_report"],
        "siem",
        fixture["input"]["connector_config"],
    ).to_dict()
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    mode_enum = schema["$defs"]["connector_dry_run"]["properties"]["mode"]["enum"]
    readiness_enum = schema["$defs"]["connector_dry_run"]["properties"]["readiness_effect"]["enum"]

    assert result["mode"] in mode_enum
    assert result["readiness_effect"] in readiness_enum
    assert "siem" in mode_enum
    assert "warehouse" in mode_enum
    assert "ticketing" in mode_enum
    assert "non_gating_failure" in readiness_enum


def test_ops_connector_preserves_sourceRefs() -> None:
    fixture = load_fixture("siem-export")
    result = build_ops_connector(
        fixture["input"]["enterprise_control_report"],
        "siem",
        fixture["input"]["connector_config"],
    ).to_dict()

    assert result["sourceRefs"]
    assert fixture["input"]["enterprise_control_report"]["sourceRefs"][0] in result["sourceRefs"]


def test_canonical_safe_payload_fixtures() -> None:
    cases = [
        ("siem-safe-event", "siem"),
        ("warehouse-safe-row", "warehouse"),
        ("ticket-safe-summary", "ticketing"),
        ("support-safe-bundle", "support"),
    ]
    for fixture_name, mode in cases:
        fixture = load_fixture(fixture_name)
        result = build_ops_connector(
            fixture["input"]["enterprise_control_report"],
            mode,
            fixture["input"]["connector_config"],
        ).to_dict()

        assert result["mode"] == fixture["expected"]["mode"]
        assert result["status"] == fixture["expected"]["status"]
        assert result["readiness_effect"] == fixture["expected"]["readiness_effect"]
        assert result["payload_kind"] == fixture["expected"]["payload_kind"]
        assert result["simulated_actions"]
        assert result["denied_actions"] == []


def test_unsafe_artifact_export_is_hard_dq_and_redacted() -> None:
    fixture = load_fixture("unsafe-artifact-export")
    result = build_ops_connector(
        fixture["input"]["enterprise_control_report"],
        "support",
        fixture["input"]["connector_config"],
    ).to_dict()

    assert result["status"] == fixture["expected"]["status"]
    assert result["readiness_effect"] == fixture["expected"]["readiness_effect"]
    assert result["denied_actions"][0]["action"] == fixture["expected"]["denied_action"]
    assert fixture["expected"]["forbidden"] not in json.dumps(result, sort_keys=True)


def test_canonical_live_network_attempt_is_hold() -> None:
    fixture = load_fixture("live-network-attempt")
    result = build_ops_connector(
        fixture["input"]["enterprise_control_report"],
        "siem",
        fixture["input"]["connector_config"],
    ).to_dict()

    assert result["status"] == fixture["expected"]["status"]
    assert result["readiness_effect"] == fixture["expected"]["readiness_effect"]
    assert result["denied_actions"][0]["action"] == fixture["expected"]["denied_action"]
