from __future__ import annotations

import json
from pathlib import Path

from hate.post_poc.observability import (
    build_incident_response_packet,
    build_observability_report,
    evaluate_observability_fixture,
    write_incident_response_packet,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "post-poc" / "observability"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "observability-report.schema.json"
INCIDENT_PACKET_SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "incident-response-packet.schema.json"
SLO_SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "slo-burn-rate-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    slo_schema = json.loads(SLO_SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "observability-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    assert report["slo_burn_rate_report"]["record_type"] == "slo-burn-rate-report"
    assert set(slo_schema["required"]) <= set(report["slo_burn_rate_report"])
    assert isinstance(report["slo_burn_rate_report"]["burn_rate"], float)
    assert report["incident_lifecycle_record"]["record_type"] == "incident-lifecycle-record"
    assert report["post_incident_evidence_pack"]["record_type"] == "post-incident-evidence-pack"
    for event in report["runtime_telemetry_events"]:
        assert event["record_type"] == "runtime-telemetry-event"
        assert {"correlation_id", "run_id", "tenant_id", "service_name", "metric_name"} <= set(event)
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def _assert_incident_packet_contract(packet: dict) -> None:
    schema = json.loads(INCIDENT_PACKET_SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(packet)
    assert packet["schema_version"] == "HATE/v1"
    assert packet["record_type"] == "incident-response-packet"
    assert packet["summary"]["action_count"] == len(packet["actions"])
    assert packet["summary"]["blocked_action_count"] == sum(1 for action in packet["actions"] if action["status"] == "blocked")
    assert packet["summary"]["finding_count"] == len(packet["findings"])
    assert packet["support_pack"]["record_type"] == "post-incident-evidence-pack"
    for action in packet["actions"]:
        assert set(schema["properties"]["actions"]["items"]["required"]) <= set(action)
        assert action["record_type"] == "incident-response-action"
        assert action["status"] in {"ready", "blocked"}
    for finding in packet["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_task_postpoc_015_canonical_fixture_paths_exist() -> None:
    for name in [
        "telemetry-valid",
        "raw-secret-log-denied",
        "alert-route-missing",
        "slo-burn-rate-breach",
        "incident-review-missing",
    ]:
        assert (FIXTURES / name / "fixture.json").is_file()


def test_telemetry_valid_passes_with_safe_support_pack() -> None:
    result = evaluate_observability_fixture(_fixture("telemetry-valid"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["report"]["summary"]["support_bundle_safe"] is True
    _assert_report_contract(result["report"])


def test_raw_secret_log_denied_before_support_export() -> None:
    result = evaluate_observability_fixture(_fixture("raw-secret-log-denied"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "observability_raw_secret_log"
    assert result["report"]["post_incident_evidence_pack"]["support_bundle_safe"] is False


def test_alert_route_missing_holds_when_slo_is_firing() -> None:
    result = evaluate_observability_fixture(_fixture("alert-route-missing"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "observability_alert_route_missing"
    assert "observability_slo_breach" in _codes(result["report"])


def test_slo_burn_rate_breach_holds_with_route_and_owner() -> None:
    result = evaluate_observability_fixture(_fixture("slo-burn-rate-breach"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "observability_slo_breach"
    assert "incident_owner_missing" not in _codes(result["report"])


def test_incident_review_missing_holds_closed_incident() -> None:
    result = evaluate_observability_fixture(_fixture("incident-review-missing"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "incident_review_missing"


def test_correlation_id_missing_holds() -> None:
    report = build_observability_report({
        "telemetry": [
            {"run_id": "run-no-corr", "tenant_id": "tenant-a", "service_name": "hate-api", "metric_name": "error.rate"}
        ],
        "slo": {"slo_id": "slo-api", "burn_rate": 0.1, "alert_status": "ok"},
        "incident": {"incident_state": "none"},
    })

    assert report["overall_status"] == "hold"
    assert "observability_correlation_id_missing" in _codes(report)


def test_active_incident_requires_owner() -> None:
    report = build_observability_report({
        "telemetry": [
            {"correlation_id": "corr-owner", "run_id": "run-owner", "tenant_id": "tenant-a", "service_name": "hate-api", "metric_name": "error.rate", "redaction_report_ref": "artifact://redaction/owner"}
        ],
        "slo": {"slo_id": "slo-api", "burn_rate": 0.4, "alert_status": "ok", "alert_route_ref": "route://ops"},
        "incident": {"incident_id": "inc-owner", "incident_state": "active", "owner": "", "severity": "high", "timeline_refs": ["artifact://incident/owner/timeline"], "decision_ref": "artifact://incident/owner/decision"},
        "support_pack": {"evidence_refs": ["artifact://support/owner"], "support_bundle_safe": True, "redaction_report_ref": "artifact://redaction/owner"},
    })

    assert report["overall_status"] == "hold"
    assert "incident_owner_missing" in _codes(report)


def test_incident_requires_timeline_and_decision_refs() -> None:
    report = build_observability_report({
        "telemetry": [
            {"correlation_id": "corr-timeline", "run_id": "run-timeline", "tenant_id": "tenant-a", "service_name": "hate-api", "metric_name": "error.rate", "redaction_report_ref": "artifact://redaction/timeline"}
        ],
        "slo": {"slo_id": "slo-api", "burn_rate": 0.4, "alert_status": "ok", "alert_route_ref": "route://ops"},
        "incident": {"incident_id": "inc-timeline", "incident_state": "active", "owner": "ops-owner", "severity": "high"},
        "support_pack": {"evidence_refs": ["artifact://support/timeline"], "support_bundle_safe": True, "redaction_report_ref": "artifact://redaction/timeline"},
    })

    assert report["overall_status"] == "hold"
    assert "incident_review_missing" in _codes(report)


def test_observability_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["observability-report"] == "schemas/HATE/v1/observability-report.schema.json"
    assert records["incident-response-packet"] == "schemas/HATE/v1/incident-response-packet.schema.json"
    assert records["slo-burn-rate-report"] == "schemas/HATE/v1/slo-burn-rate-report.schema.json"


def test_incident_response_packet_ready_for_valid_incident() -> None:
    packet = build_incident_response_packet(_fixture("telemetry-valid")["input"], source_refs=["fixture://observability/packet-ready"])

    assert packet["record_type"] == "incident-response-packet"
    assert packet["summary"]["ready_for_response"] is True
    assert packet["summary"]["blocked_action_count"] == 0
    assert packet["findings"] == []
    assert {action["status"] for action in packet["actions"]} == {"ready"}
    assert packet["sourceRefs"] == ["fixture://observability/packet-ready"]
    _assert_incident_packet_contract(packet)


def test_incident_response_packet_blocks_missing_alert_route() -> None:
    packet = build_incident_response_packet(_fixture("alert-route-missing")["input"])

    assert packet["summary"]["ready_for_response"] is False
    blocked = [action["action_id"] for action in packet["actions"] if action["status"] == "blocked"]
    assert "route_alert" in blocked
    assert "incident_response_blocked_by_observability_findings" in _codes(packet)


def test_incident_response_packet_blocks_raw_secret_support_pack() -> None:
    packet = build_incident_response_packet(_fixture("raw-secret-log-denied")["input"])

    assert packet["summary"]["support_bundle_safe"] is False
    blocked = [action["action_id"] for action in packet["actions"] if action["status"] == "blocked"]
    assert "export_safe_support_pack" in blocked


def test_incident_response_packet_blocks_missing_post_incident_review() -> None:
    packet = build_incident_response_packet(_fixture("incident-review-missing")["input"])

    blocked = [action["action_id"] for action in packet["actions"] if action["status"] == "blocked"]
    assert "post_incident_review" in blocked
    assert "incident_response_action_blocked" in _codes(packet)


def test_incident_response_packet_artifact_write_contract(tmp_path: Path) -> None:
    packet = build_incident_response_packet(_fixture("telemetry-valid")["input"], source_refs=["fixture://observability/packet-artifact"])
    out_path = tmp_path / "incident-response-packet.json"

    artifact = write_incident_response_packet(packet, out_path)

    assert artifact["record_type"] == "incident-response-packet-artifact"
    assert artifact["action_count"] == len(packet["actions"])
    assert artifact["sourceRefs"] == ["fixture://observability/packet-artifact"]
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["record_type"] == "incident-response-packet"
    assert written["summary"]["ready_for_response"] is True
    _assert_incident_packet_contract(written)
