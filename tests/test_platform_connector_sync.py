"""Tests for platform connector sync payload evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from hate.connectors import build_connector_sync_report
from hate.p0a_schema import _validate_schema_value


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "platform" / "connectors"
SCHEMAS = ROOT / "schemas" / "HATE" / "v1"


def test_platform_connector_sync_fixture_paths_exist() -> None:
    for name in [
        "github-check-safe-summary",
        "slack-notification-failed",
        "inbound-close-denied",
        "idempotent-retry",
        "redaction-before-send",
    ]:
        assert (FIXTURES / name / "fixture.json").exists()


def test_github_check_safe_summary_passes() -> None:
    fixture = _fixture("github-check-safe-summary")

    report = build_connector_sync_report(fixture["input"], fixture["fixture_id"])

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert report["summary"]["accepted_count"] == fixture["expected"]["accepted_count"]
    assert report["generated_operating_events"][0]["event_type"] == fixture["expected"]["generated_event_type"]
    assert "raw_artifact_body" not in json.dumps(report["accepted_payloads"], sort_keys=True)
    assert "fixtures/platform/connectors/github-check-safe-summary/fixture.json#payload" in report["sourceRefs"]


def test_slack_retryable_failure_generates_notification_failed_event() -> None:
    fixture = _fixture("slack-notification-failed")

    report = build_connector_sync_report(fixture["input"], fixture["fixture_id"])
    event = report["generated_operating_events"][0]

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert event["event_type"] == fixture["expected"]["generated_event_type"]
    assert event["sync_status"] == fixture["expected"]["sync_status"]


def test_inbound_close_ack_cannot_mutate_canonical_state() -> None:
    fixture = _fixture("inbound-close-denied")

    report = build_connector_sync_report(fixture["input"], fixture["fixture_id"])

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert fixture["expected"]["finding_code"] in {finding["code"] for finding in report["findings"]}
    assert report["generated_operating_events"][0]["event_type"] == fixture["expected"]["generated_event_type"]


def test_idempotent_retry_skips_duplicate_payload() -> None:
    fixture = _fixture("idempotent-retry")

    report = build_connector_sync_report(fixture["input"], fixture["fixture_id"])

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert report["summary"]["accepted_count"] == fixture["expected"]["accepted_count"]
    assert report["summary"]["skipped_duplicate_count"] == fixture["expected"]["skipped_duplicate_count"]
    assert report["findings"] == []


def test_redaction_before_send_blocks_raw_artifact_fields() -> None:
    fixture = _fixture("redaction-before-send")

    report = build_connector_sync_report(fixture["input"], fixture["fixture_id"])

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert report["summary"]["accepted_count"] == fixture["expected"]["accepted_count"]
    assert report["summary"]["denied_count"] == fixture["expected"]["denied_count"]
    assert fixture["expected"]["finding_code"] in {finding["code"] for finding in report["findings"]}
    assert "secret=abc123" not in json.dumps(report["accepted_payloads"], sort_keys=True)


def test_platform_connector_sync_schema_registered() -> None:
    schema = json.loads((SCHEMAS / "platform-connector-sync-report.schema.json").read_text(encoding="utf-8"))
    operating_schema = json.loads((SCHEMAS / "operating-event-record.schema.json").read_text(encoding="utf-8"))
    registry = json.loads((SCHEMAS / "schema-registry.json").read_text(encoding="utf-8"))

    assert schema["properties"]["record_type"]["const"] == "platform-connector-sync-report"
    assert "tracker_sync_failed" in operating_schema["properties"]["event_type"]["enum"]
    assert any(record["record_type"] == "platform-connector-sync-report" for record in registry["records"])


def test_platform_connector_sync_report_matches_artifact_schema() -> None:
    schema = json.loads((SCHEMAS / "platform-connector-sync-report.schema.json").read_text(encoding="utf-8"))

    for fixture_name in ["github-check-safe-summary", "inbound-close-denied", "idempotent-retry"]:
        fixture = _fixture(fixture_name)
        report = build_connector_sync_report(fixture["input"], fixture["fixture_id"])
        assert _validate_schema_value(report, schema, "$") == []


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))
