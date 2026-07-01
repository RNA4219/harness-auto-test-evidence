"""Platform dashboard view models for operating records and connector sync."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def build_findings_queue_view_model(
    operating_projection_report: dict[str, Any],
    *,
    scope: str = "default",
    permissions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the Findings Queue view from canonical operating projection."""
    records = [
        _finding_queue_item(record)
        for record in operating_projection_report.get("records", [])
        if record.get("entity_kind") in {"finding", "policy_drift", "external_hold"}
        and record.get("status") in {"open", "expired", "accepted"}
    ]
    records.sort(key=lambda item: (item["due_date"] or "9999-12-31", _severity_rank(item["severity"]), item["operating_record_id"]))
    findings = operating_projection_report.get("findings", [])
    return _view(
        view_id="findings-queue",
        scope=scope,
        permissions=permissions,
        summary={
            "open_count": sum(1 for item in records if item["status"] == "open"),
            "expired_count": sum(1 for item in records if item["status"] == "expired"),
            "missing_owner_count": sum(1 for item in records if not item["owner"]),
            "finding_count": len(findings),
        },
        items=records,
        selected_item=records[0] if records else None,
        sourceRefs=operating_projection_report.get("sourceRefs", []),
        errors=[_error_from_finding(finding) for finding in findings],
    )


def build_risk_debt_board_view_model(
    operating_projection_report: dict[str, Any],
    *,
    scope: str = "default",
    permissions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the Risk Debt Board view from operating risk debt records."""
    items = [
        _risk_debt_item(record)
        for record in operating_projection_report.get("records", [])
        if record.get("entity_kind") == "risk_debt"
    ]
    items.sort(key=lambda item: (item["expiry_date"] or "9999-12-31", _severity_rank(item["severity"]), item["operating_record_id"]))
    return _view(
        view_id="risk-debt-board",
        scope=scope,
        permissions=permissions,
        summary={
            "accepted_count": sum(1 for item in items if item["status"] == "accepted"),
            "expired_count": sum(1 for item in items if item["status"] == "expired"),
            "resolved_count": sum(1 for item in items if item["status"] == "resolved"),
            "evidence_linked_count": sum(1 for item in items if item["evidence_refs"]),
        },
        items=items,
        selected_item=items[0] if items else None,
        sourceRefs=operating_projection_report.get("sourceRefs", []),
        errors=[],
    )


def build_operating_manual_review_queue_view_model(
    operating_projection_report: dict[str, Any],
    *,
    scope: str = "default",
    permissions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build Manual Review Queue from operating manual_review records."""
    items = [
        _manual_review_item(record)
        for record in operating_projection_report.get("records", [])
        if record.get("entity_kind") == "manual_review"
    ]
    items.sort(key=lambda item: (item["expiry_date"] or "9999-12-31", item["operating_record_id"]))
    return _view(
        view_id="manual-review-queue",
        scope=scope,
        permissions=permissions,
        summary={
            "pending_count": sum(1 for item in items if item["status"] == "open"),
            "blocking_count": sum(1 for item in items if item["blocking"]),
            "missing_decision_count": sum(1 for item in items if not item["required_decision"]),
        },
        items=items,
        selected_item=items[0] if items else None,
        sourceRefs=operating_projection_report.get("sourceRefs", []),
        errors=[],
    )


def build_connector_sync_view_model(
    connector_sync_report: dict[str, Any],
    *,
    scope: str = "default",
    permissions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a connector sync mirror view without exposing unsafe payload body."""
    payloads = [_connector_item(payload, accepted=True) for payload in connector_sync_report.get("accepted_payloads", [])]
    payloads.extend(_connector_item(payload, accepted=False) for payload in connector_sync_report.get("denied_payloads", []))
    payloads.extend(_connector_item(payload, accepted=False, skipped=True) for payload in connector_sync_report.get("skipped_duplicate_payloads", []))
    return _view(
        view_id="connector-sync",
        scope=scope,
        permissions=permissions,
        summary={
            "accepted_count": connector_sync_report.get("summary", {}).get("accepted_count", 0),
            "denied_count": connector_sync_report.get("summary", {}).get("denied_count", 0),
            "skipped_duplicate_count": connector_sync_report.get("summary", {}).get("skipped_duplicate_count", 0),
            "generated_event_count": connector_sync_report.get("summary", {}).get("generated_event_count", 0),
        },
        items=payloads,
        selected_item=payloads[0] if payloads else None,
        sourceRefs=connector_sync_report.get("sourceRefs", []),
        errors=[_error_from_finding(finding) for finding in connector_sync_report.get("findings", [])],
        redactions=[{"reason": "connector_payload_safe_summary_only", "field": "payload"}],
    )


def _view(
    *,
    view_id: str,
    scope: str,
    permissions: dict[str, Any] | None,
    summary: dict[str, Any],
    items: list[dict[str, Any]],
    selected_item: dict[str, Any] | None,
    sourceRefs: list[str],
    errors: list[dict[str, Any]],
    redactions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "HATE/v1",
        "record_type": "platform-dashboard-view-model",
        "view_id": view_id,
        "scope": scope,
        "generated_at": datetime.now(UTC).isoformat(),
        "stale": False,
        "permissions": permissions or {"can_read": True, "can_view_raw": False},
        "summary": summary,
        "items": items,
        "selected_item": selected_item,
        "sourceRefs": sourceRefs,
        "redactions": redactions or [],
        "errors": errors,
    }


def _finding_queue_item(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "operating_record_id": record.get("operating_record_id", ""),
        "entity_kind": record.get("entity_kind", ""),
        "status": record.get("status", ""),
        "severity": record.get("severity", ""),
        "readiness_effect": record.get("readiness_effect", ""),
        "owner": record.get("owner", ""),
        "due_date": record.get("due_date", ""),
        "sourceRefs": record.get("sourceRefs", []),
        "detail_available": True,
    }


def _risk_debt_item(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "operating_record_id": record.get("operating_record_id", ""),
        "status": record.get("status", ""),
        "severity": record.get("severity", ""),
        "owner": record.get("owner", ""),
        "expiry_date": record.get("expiry_date", ""),
        "evidence_refs": record.get("evidence_refs", []),
        "decision_basis": record.get("decision_basis", []),
        "sourceRefs": record.get("sourceRefs", []),
    }


def _manual_review_item(record: dict[str, Any]) -> dict[str, Any]:
    review = record.get("manual_review", {})
    return {
        "operating_record_id": record.get("operating_record_id", ""),
        "status": record.get("status", ""),
        "severity": record.get("severity", ""),
        "owner": record.get("owner", ""),
        "expiry_date": record.get("expiry_date", ""),
        "required_decision": review.get("required_decision", ""),
        "blocking": bool(review.get("blocking", False)),
        "decision_reason": review.get("decision_reason", ""),
        "sourceRefs": record.get("sourceRefs", []),
    }


def _connector_item(payload: dict[str, Any], *, accepted: bool, skipped: bool = False) -> dict[str, Any]:
    return {
        "sync_id": payload.get("sync_id", ""),
        "operating_record_id": payload.get("operating_record_id", ""),
        "connector_id": payload.get("connector_id", ""),
        "external_system": payload.get("external_system", ""),
        "direction": payload.get("direction", ""),
        "operation": payload.get("operation", ""),
        "state": payload.get("state", ""),
        "idempotency_key": payload.get("idempotency_key", ""),
        "payload_hash": payload.get("payload_hash", ""),
        "safe_summary": payload.get("safe_summary", {}),
        "accepted": accepted,
        "skipped_duplicate": skipped,
        "sourceRefs": payload.get("sourceRefs", []),
    }


def _error_from_finding(finding: dict[str, Any]) -> dict[str, Any]:
    return {
        "code": finding.get("code", ""),
        "severity": finding.get("severity", "info"),
        "message": finding.get("message", ""),
        "sourceRefs": finding.get("sourceRefs", []),
    }


def _severity_rank(severity: str) -> int:
    return {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(severity, 4)
