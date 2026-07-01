"""Tests for platform operations operating model packets."""

from __future__ import annotations

import json
from pathlib import Path

from hate.operations import build_operating_projection_report


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "platform" / "operations"
STORE_FIXTURES = ROOT / "fixtures" / "platform" / "store"
SCHEMAS = ROOT / "schemas" / "HATE" / "v1"


def test_operating_model_fixture_paths_exist() -> None:
    for name in [
        "debt-resolved-with-evidence",
        "finding-owner-due-date",
        "accepted-debt-expired",
        "accepted-debt-invalid-expiry",
        "dedupe-target-missing",
        "manual-review-no-evidence",
        "inbound-tracker-close-denied",
        "notification-failure-retains-finding",
        "retention-legal-hold-rebuild",
        "blocking-finding-missing-owner-due",
    ]:
        assert (FIXTURES / name / "fixture.json").exists()
    for name in [
        "projection-rebuild-gap",
        "projection-rebuild-hash-mismatch",
        "projection-rebuild-sorted",
    ]:
        assert (STORE_FIXTURES / name / "fixture.json").exists()


def test_debt_resolved_with_evidence_reduces_to_resolved() -> None:
    fixture = _fixture("debt-resolved-with-evidence")

    report = build_operating_projection_report(fixture["input"], fixture["fixture_id"])
    record = report["records"][0]

    assert report["record_type"] == fixture["expected"]["record_type"]
    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert record["status"] == fixture["expected"]["status"]
    assert record["last_event_id"] == fixture["expected"]["last_event_id"]
    assert fixture["expected"]["evidence_ref"] in record["evidence_refs"]
    assert report["findings"] == []


def test_accepted_debt_missing_owner_or_expiry_holds() -> None:
    fixture = _fixture("finding-owner-due-date")

    report = build_operating_projection_report(fixture["input"], fixture["fixture_id"])
    record = report["records"][0]

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert record["status"] == fixture["expected"]["status"]
    assert set(fixture["expected"]["finding_codes"]) <= {finding["code"] for finding in report["findings"]}


def test_accepted_debt_expiry_is_time_based_hold() -> None:
    fixture = _fixture("accepted-debt-expired")

    report = build_operating_projection_report(fixture["input"], fixture["fixture_id"])
    record = report["records"][0]

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert record["status"] == fixture["expected"]["status"]
    assert fixture["expected"]["finding_code"] in {finding["code"] for finding in report["findings"]}


def test_accepted_debt_invalid_expiry_holds() -> None:
    fixture = _fixture("accepted-debt-invalid-expiry")

    report = build_operating_projection_report(fixture["input"], fixture["fixture_id"])
    record = report["records"][0]

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert record["status"] == fixture["expected"]["status"]
    assert fixture["expected"]["finding_code"] in {finding["code"] for finding in report["findings"]}


def test_dedupe_target_must_exist() -> None:
    fixture = _fixture("dedupe-target-missing")

    report = build_operating_projection_report(fixture["input"], fixture["fixture_id"])
    record = report["records"][0]

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert record["status"] == fixture["expected"]["status"]
    assert fixture["expected"]["finding_code"] in {finding["code"] for finding in report["findings"]}


def test_manual_review_decision_requires_evidence() -> None:
    fixture = _fixture("manual-review-no-evidence")

    report = build_operating_projection_report(fixture["input"], fixture["fixture_id"])
    record = report["records"][0]

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert record["status"] == fixture["expected"]["status"]
    assert record["manual_review"]["required_decision"] == "approve_or_reject_debt"
    assert record["manual_review"]["blocking"] is True
    assert fixture["expected"]["finding_code"] in {finding["code"] for finding in report["findings"]}


def test_inbound_tracker_close_cannot_resolve_canonical_record() -> None:
    fixture = _fixture("inbound-tracker-close-denied")

    report = build_operating_projection_report(fixture["input"], fixture["fixture_id"])
    record = report["records"][0]

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert record["status"] == fixture["expected"]["status"]
    assert record["tracker_syncs"][0]["external_status"] == "closed"
    assert fixture["expected"]["finding_code"] in {finding["code"] for finding in report["findings"]}


def test_notification_failure_retains_open_finding() -> None:
    fixture = _fixture("notification-failure-retains-finding")

    report = build_operating_projection_report(fixture["input"], fixture["fixture_id"])
    record = report["records"][0]

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert record["status"] == fixture["expected"]["status"]
    assert record["notifications"][0]["delivery_status"] == "failed_retryable"
    assert fixture["expected"]["finding_code"] in {finding["code"] for finding in report["findings"]}


def test_retention_legal_hold_and_rebuild_metadata_survive_projection() -> None:
    fixture = _fixture("retention-legal-hold-rebuild")

    report = build_operating_projection_report(fixture["input"], fixture["fixture_id"])
    record = report["records"][0]

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert record["status"] == fixture["expected"]["status"]
    assert record["expiry_date"] == "2026-08-01"
    assert record["retention_events"][0]["retention_policy_id"] == fixture["expected"]["retention_policy_id"]
    assert record["legal_holds"][0]["legal_hold_id"] == fixture["expected"]["legal_hold_id"]
    assert record["rebuild_events"][0]["rebuild_id"] == fixture["expected"]["rebuild_id"]
    assert report["findings"] == []


def test_blocking_record_requires_owner_and_due_date() -> None:
    fixture = _fixture("blocking-finding-missing-owner-due")

    report = build_operating_projection_report(fixture["input"], fixture["fixture_id"])
    record = report["records"][0]

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert record["status"] == fixture["expected"]["status"]
    assert fixture["expected"]["finding_code"] in {finding["code"] for finding in report["findings"]}


def test_projection_rebuild_detects_event_sequence_gap() -> None:
    fixture = _store_fixture("projection-rebuild-gap")

    report = build_operating_projection_report(fixture["input"], fixture["fixture_id"])

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert report["summary"]["event_stream_finding_count"] == fixture["expected"]["event_stream_finding_count"]
    assert fixture["expected"]["finding_code"] in {finding["code"] for finding in report["findings"]}


def test_projection_rebuild_detects_hash_continuity_mismatch() -> None:
    fixture = _store_fixture("projection-rebuild-hash-mismatch")

    report = build_operating_projection_report(fixture["input"], fixture["fixture_id"])

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert report["summary"]["event_stream_finding_count"] == fixture["expected"]["event_stream_finding_count"]
    assert fixture["expected"]["finding_code"] in {finding["code"] for finding in report["findings"]}


def test_projection_rebuild_sorts_events_by_sequence_before_reduce() -> None:
    fixture = _store_fixture("projection-rebuild-sorted")

    report = build_operating_projection_report(fixture["input"], fixture["fixture_id"])
    record = report["records"][0]

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert report["events"][0]["event_id"] == fixture["expected"]["first_event_id"]
    assert record["status"] == fixture["expected"]["status"]
    assert record["last_event_id"] == fixture["expected"]["last_event_id"]
    assert report["summary"]["event_stream_finding_count"] == fixture["expected"]["event_stream_finding_count"]


def test_operating_schema_registry_contract() -> None:
    event_schema = json.loads((SCHEMAS / "operating-event-record.schema.json").read_text(encoding="utf-8"))
    record_schema = json.loads((SCHEMAS / "operating-finding-record.schema.json").read_text(encoding="utf-8"))
    report_schema = json.loads((SCHEMAS / "operating-projection-report.schema.json").read_text(encoding="utf-8"))
    registry = json.loads((SCHEMAS / "schema-registry.json").read_text(encoding="utf-8"))

    assert event_schema["properties"]["record_type"]["const"] == "operating-event-record"
    assert record_schema["properties"]["record_type"]["const"] == "operating-finding-record"
    assert report_schema["properties"]["record_type"]["const"] == "operating-projection-report"
    assert "external_status" in event_schema["properties"]
    assert "blocking" in event_schema["properties"]
    assert "occurred_at" in event_schema["properties"]
    assert "tracker_syncs" in record_schema["properties"]
    assert any(record["record_type"] == "operating-event-record" for record in registry["records"])
    assert any(record["record_type"] == "operating-finding-record" for record in registry["records"])
    assert any(record["record_type"] == "operating-projection-report" for record in registry["records"])


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _store_fixture(name: str) -> dict:
    return json.loads((STORE_FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))
