"""Tests for HATE-GAP-030 notification delivery evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from hate.expansion.notifications import build_notification_report, evaluate_notification_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "expansion" / "notifications"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "notification-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "notification-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_canonical_gap_030_fixture_paths_exist() -> None:
    assert (FIXTURES / "signed-delivery" / "fixture.json").is_file()
    assert (FIXTURES / "unsigned-webhook-denied" / "fixture.json").is_file()


def test_signed_delivery_fixture_passes() -> None:
    result = evaluate_notification_fixture(_fixture("signed-delivery"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "none"
    _assert_report_contract(result["report"])


def test_unsigned_webhook_denied_fixture_holds() -> None:
    result = evaluate_notification_fixture(_fixture("unsigned-webhook-denied"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "notification_unsigned_webhook_denied"
    assert result["readiness_effect"] == "hold"
    _assert_report_contract(result["report"])


def test_missing_event_taxonomy_holds() -> None:
    report = build_notification_report({
        "event_taxonomy_defined": False,
        "signing_enabled": True,
        "retry_schedule_defined": True,
        "dedupe_enabled": True,
        "dead_letter_state_defined": True,
        "tenant_scoped_delivery": True,
        "webhook_url": "https://example.com/webhook",
        "signature_verified": True,
    })

    assert report["overall_status"] == "hold"
    assert "notification_event_taxonomy_missing" in _codes(report)


def test_missing_retry_schedule_holds() -> None:
    report = build_notification_report({
        "event_taxonomy_defined": True,
        "signing_enabled": True,
        "retry_schedule_defined": False,
        "dedupe_enabled": True,
        "dead_letter_state_defined": True,
        "tenant_scoped_delivery": True,
        "webhook_url": "https://example.com/webhook",
        "signature_verified": True,
    })

    assert report["overall_status"] == "hold"
    assert "notification_retry_schedule_missing" in _codes(report)


def test_missing_dead_letter_handling_holds() -> None:
    report = build_notification_report({
        "event_taxonomy_defined": True,
        "signing_enabled": True,
        "retry_schedule_defined": True,
        "dedupe_enabled": True,
        "dead_letter_state_defined": False,
        "tenant_scoped_delivery": True,
        "webhook_url": "https://example.com/webhook",
        "signature_verified": True,
    })

    assert report["overall_status"] == "hold"
    assert "notification_dead_letter_missing" in _codes(report)


def test_notification_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["notification-report"] == "schemas/HATE/v1/notification-report.schema.json"
