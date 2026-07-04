from __future__ import annotations

import json
from pathlib import Path

from hate.post_poc.notifications import (
    build_notification_delivery_report,
    build_notification_routing_plan,
    evaluate_notification_delivery_fixture,
    write_notification_routing_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "post-poc" / "notifications"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "notification-delivery-report.schema.json"
ROUTING_SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "notification-routing-manifest.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "notification-delivery-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    assert report["delivery_plan"]["record_type"] == "notification-delivery-plan"
    for attempt in report["delivery_attempts"]:
        assert attempt["record_type"] == "notification-delivery-attempt"
        assert attempt["sourceRefs"]
    for event in report["dead_letter_events"]:
        assert event["record_type"] == "notification-dead-letter-event"
        assert event["sourceRefs"]
    for audit in report["audit_events"]:
        assert audit["record_type"] == "notification-audit-event"
        assert audit["sourceRefs"]
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def _assert_routing_manifest_contract(manifest: dict) -> None:
    schema = json.loads(ROUTING_SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(manifest)
    assert manifest["schema_version"] == "HATE/v1"
    assert manifest["record_type"] == "notification-routing-manifest"
    for entry in manifest["routing_entries"]:
        assert set(schema["properties"]["routing_entries"]["items"]["required"]) <= set(entry)
        assert entry["record_type"] == "notification-routing-entry"
        assert entry["routing_role"] in {"primary", "escalation"}
        assert entry["sourceRefs"]


def test_task_postpoc_003_canonical_fixture_paths_exist() -> None:
    for name in [
        "slack-delivered",
        "webhook-signed",
        "duplicate-suppressed",
        "dead-lettered",
        "unsafe-payload-denied",
    ]:
        assert (FIXTURES / name / "fixture.json").is_file()


def test_slack_delivered_passes_and_preserves_open_operating_record() -> None:
    result = evaluate_notification_delivery_fixture(_fixture("slack-delivered"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["report"]["delivery_plan"]["delivery_status"] == "delivered"
    assert result["report"]["summary"]["operating_record_status_after"] == "open"
    _assert_report_contract(result["report"])


def test_webhook_signed_passes_without_exposing_secret() -> None:
    result = evaluate_notification_delivery_fixture(_fixture("webhook-signed"))

    assert result["status"] == "pass"
    signature_ref = result["report"]["delivery_attempts"][0]["signature_ref"]
    assert signature_ref == "secret-ref://signing-key/webhook-a"
    assert "token=" not in json.dumps(result["report"])


def test_duplicate_suppressed_holds_but_preserves_audit_event() -> None:
    result = evaluate_notification_delivery_fixture(_fixture("duplicate-suppressed"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "notification_duplicate_suppressed"
    assert result["report"]["delivery_attempts"] == []
    assert result["report"]["audit_events"][0]["event_type"] == "duplicate_suppressed"


def test_dead_lettered_holds_and_writes_dead_letter_event() -> None:
    result = evaluate_notification_delivery_fixture(_fixture("dead-lettered"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "notification_delivery_failed"
    assert "notification_dead_lettered" in _codes(result["report"])
    assert result["report"]["dead_letter_events"][0]["attempt"] == 3
    assert result["report"]["summary"]["operating_record_status_after"] == "open"


def test_unsafe_payload_is_denied() -> None:
    result = evaluate_notification_delivery_fixture(_fixture("unsafe-payload-denied"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "notification_payload_unsafe"
    assert "notification_delivery_failed" in _codes(result["report"])


def test_webhook_signature_missing_holds() -> None:
    report = build_notification_delivery_report({
        "plan": {
            "notification_id": "notify-webhook-missing",
            "operating_record_id": "finding:OPEN",
            "delivery_target": "webhook",
            "target_ref": "webhook://system",
            "dedupe_key": "k",
            "payload_hash": "sha256:p",
            "redaction_report_ref": "artifact://redaction/report.json",
        },
        "attempts": [{"delivery_status": "delivered"}],
    })

    assert report["overall_status"] == "hold"
    assert "notification_signature_missing" in _codes(report)


def test_target_missing_holds() -> None:
    report = build_notification_delivery_report({
        "plan": {
            "notification_id": "notify-target-missing",
            "operating_record_id": "finding:OPEN",
            "delivery_target": "unsupported",
            "target_ref": "",
            "dedupe_key": "",
            "payload_hash": "",
            "redaction_report_ref": "artifact://redaction/report.json",
        }
    })

    assert report["overall_status"] == "hold"
    assert "notification_target_missing" in _codes(report)


def test_retry_scheduled_requires_next_retry_at() -> None:
    report = build_notification_delivery_report({
        "plan": {
            "notification_id": "notify-retry-missing",
            "operating_record_id": "finding:OPEN",
            "delivery_target": "email",
            "target_ref": "mailto:owner@example.com",
            "dedupe_key": "k",
            "payload_hash": "sha256:p",
            "redaction_report_ref": "artifact://redaction/report.json",
        },
        "attempts": [{"delivery_status": "retry_scheduled", "error_code": "network"}],
    })

    assert report["overall_status"] == "hold"
    assert _codes(report).count("notification_delivery_failed") >= 1


def test_notification_delivery_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["notification-delivery-report"] == "schemas/HATE/v1/notification-delivery-report.schema.json"
    assert records["notification-routing-manifest"] == "schemas/HATE/v1/notification-routing-manifest.schema.json"


def test_notification_routing_plan_resolves_owner_and_team_subscribers() -> None:
    plan = build_notification_routing_plan({
        "operating_record": {
            "operating_record_id": "finding:OPEN-1",
            "severity": "high",
            "owner": "alice@example.com",
            "team": "quality",
            "payload_hash": "sha256:payload",
            "redaction_report_ref": "artifact://redaction/report.json",
            "sourceRef": "finding://OPEN-1",
        },
        "subscribers": [
            {
                "subscriber_id": "owner-alice",
                "owner": "alice@example.com",
                "delivery_target": "slack_dm",
                "target_ref": "slack://dm/alice",
                "sourceRef": "subscriber://alice",
            },
            {
                "subscriber_id": "team-quality",
                "team": "quality",
                "delivery_target": "slack_channel",
                "target_ref": "slack://channel/quality",
                "sourceRef": "subscriber://quality",
            },
        ],
    }, source_refs=["fixture://notifications/routing"])

    assert plan["record_type"] == "notification-routing-plan"
    assert plan["summary"]["primary_count"] == 2
    assert plan["summary"]["escalation_count"] == 0
    assert plan["findings"] == []
    assert {entry["routing_role"] for entry in plan["routing_entries"]} == {"primary"}
    assert all(entry["dedupe_key"].startswith("finding:OPEN-1:") for entry in plan["routing_entries"])
    assert plan["sourceRefs"] == ["fixture://notifications/routing"]


def test_notification_routing_plan_requires_escalation_on_sla_breach() -> None:
    plan = build_notification_routing_plan({
        "operating_record": {
            "operating_record_id": "finding:SLA",
            "severity": "critical",
            "owner": "alice@example.com",
            "team": "quality",
            "sla_breached": True,
            "payload_hash": "sha256:payload",
            "redaction_report_ref": "artifact://redaction/report.json",
        },
        "subscribers": [
            {
                "subscriber_id": "owner-alice",
                "owner": "alice@example.com",
                "delivery_target": "email",
                "target_ref": "mailto:alice@example.com",
            }
        ],
    })

    assert "notification_escalation_target_missing" in _codes(plan)
    assert plan["summary"]["escalation_count"] == 0


def test_notification_routing_plan_adds_escalation_route_when_sla_breached() -> None:
    plan = build_notification_routing_plan({
        "operating_record": {
            "operating_record_id": "finding:SLA",
            "severity": "critical",
            "owner": "alice@example.com",
            "team": "quality",
            "sla_breached": True,
            "payload_hash": "sha256:payload",
            "redaction_report_ref": "artifact://redaction/report.json",
        },
        "subscribers": [
            {
                "subscriber_id": "owner-alice",
                "owner": "alice@example.com",
                "delivery_target": "email",
                "target_ref": "mailto:alice@example.com",
            },
            {
                "subscriber_id": "quality-lead",
                "team": "quality",
                "routing_role": "escalation",
                "delivery_target": "slack_channel",
                "target_ref": "slack://channel/quality-leads",
            },
        ],
    })

    assert plan["findings"] == []
    assert plan["summary"]["primary_count"] == 1
    assert plan["summary"]["escalation_count"] == 1
    assert any(entry["routing_role"] == "escalation" for entry in plan["routing_entries"])


def test_notification_routing_plan_blocks_missing_owner_or_payload_evidence() -> None:
    plan = build_notification_routing_plan({
        "operating_record": {
            "operating_record_id": "finding:NO-OWNER",
            "team": "quality",
        },
        "subscribers": [
            {
                "subscriber_id": "team-quality",
                "team": "quality",
                "delivery_target": "slack_channel",
                "target_ref": "slack://channel/quality",
            }
        ],
    })

    assert "notification_owner_missing" in _codes(plan)
    assert "notification_payload_unsafe" in _codes(plan)


def test_notification_routing_manifest_write_contract(tmp_path: Path) -> None:
    plan = build_notification_routing_plan({
        "operating_record": {
            "operating_record_id": "finding:OPEN-1",
            "owner": "alice@example.com",
            "payload_hash": "sha256:payload",
            "redaction_report_ref": "artifact://redaction/report.json",
        },
        "subscribers": [
            {
                "subscriber_id": "owner-alice",
                "owner": "alice@example.com",
                "delivery_target": "email",
                "target_ref": "mailto:alice@example.com",
            }
        ],
    }, source_refs=["fixture://notifications/manifest"])
    out_path = tmp_path / "notification-routing.json"

    artifact = write_notification_routing_manifest(plan, out_path)

    assert artifact["record_type"] == "notification-routing-manifest-artifact"
    assert artifact["routing_entry_count"] == 1
    assert artifact["sourceRefs"] == ["fixture://notifications/manifest"]
    manifest = json.loads(out_path.read_text(encoding="utf-8"))
    assert manifest["record_type"] == "notification-routing-manifest"
    _assert_routing_manifest_contract(manifest)
    assert manifest["routing_entries"][0]["target_ref"] == "mailto:alice@example.com"
