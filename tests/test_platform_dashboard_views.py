"""Tests for platform dashboard view models."""

from __future__ import annotations

import json
from pathlib import Path

from hate.dashboard import (
    build_connector_sync_view_model,
    build_findings_queue_view_model,
    build_operating_manual_review_queue_view_model,
    build_risk_debt_board_view_model,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "platform" / "dashboard"


def test_platform_dashboard_fixture_paths_exist() -> None:
    for name in [
        "findings-owner-queue",
        "manual-review-blocking",
        "risk-debt-board",
        "connector-sync-safe-summary",
    ]:
        assert (FIXTURES / name / "fixture.json").exists()


def test_findings_queue_sorts_by_owner_due_queue() -> None:
    fixture = _fixture("findings-owner-queue")

    view = build_findings_queue_view_model(fixture["input"]["operating_projection_report"])

    assert view["view_id"] == fixture["expected"]["view_id"]
    assert view["summary"]["open_count"] == fixture["expected"]["open_count"]
    assert view["items"][0]["operating_record_id"] == fixture["expected"]["first_record_id"]
    assert view["items"][0]["sourceRefs"]


def test_operating_manual_review_queue_shows_required_decision() -> None:
    fixture = _fixture("manual-review-blocking")

    view = build_operating_manual_review_queue_view_model(fixture["input"]["operating_projection_report"])
    item = view["items"][0]

    assert item["operating_record_id"] == fixture["expected"]["manual_review_record_id"]
    assert item["required_decision"] == fixture["expected"]["required_decision"]
    assert item["blocking"] is True
    assert view["summary"]["blocking_count"] == 1


def test_risk_debt_board_shows_expiry_and_evidence_refs() -> None:
    fixture = _fixture("risk-debt-board")

    view = build_risk_debt_board_view_model(fixture["input"]["operating_projection_report"])

    assert view["view_id"] == fixture["expected"]["view_id"]
    assert view["summary"]["accepted_count"] == fixture["expected"]["accepted_count"]
    assert view["summary"]["expired_count"] == fixture["expected"]["expired_count"]
    assert view["items"][0]["operating_record_id"] == fixture["expected"]["first_record_id"]
    assert view["items"][0]["evidence_refs"]


def test_connector_sync_view_uses_safe_summary_only() -> None:
    fixture = _fixture("connector-sync-safe-summary")

    view = build_connector_sync_view_model(fixture["input"]["connector_sync_report"])
    serialized = json.dumps(view, sort_keys=True)

    assert view["view_id"] == fixture["expected"]["view_id"]
    assert view["summary"]["accepted_count"] == fixture["expected"]["accepted_count"]
    assert view["items"][0]["safe_summary"]["summary"] == "safe summary"
    assert fixture["expected"]["forbidden"] not in serialized
    assert view["redactions"][0]["reason"] == "connector_payload_safe_summary_only"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))
