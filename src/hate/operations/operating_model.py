"""Append-only operating event reducer and current projection."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any


VALID_ENTITY_KINDS = {"finding", "risk_debt", "manual_review", "policy_drift", "external_hold"}
VALID_STATUSES = {"open", "accepted", "expired", "resolved", "revoked", "superseded", "merged"}
MIRROR_EVENT_TYPES = {
    "tracker_sync_requested",
    "tracker_sync_completed",
    "sla_breach_detected",
    "notification_requested",
    "notification_sent",
    "notification_failed",
    "projection_rebuilt",
    "retention_applied",
    "legal_hold_applied",
}
EVENT_STATUS = {
    "finding_opened": "open",
    "manual_review_requested": "open",
    "manual_review_decided": "resolved",
    "risk_debt_accepted": "accepted",
    "risk_debt_expired": "expired",
    "risk_debt_revoked": "revoked",
    "risk_debt_resolved": "resolved",
    "record_superseded": "superseded",
    "finding_deduplicated": "merged",
}


def reduce_operating_events(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Reduce append-only operating events into current records."""
    projection: dict[str, dict[str, Any]] = {}
    normalized = [_normalize_event(raw, sequence=index) for index, raw in enumerate(events, start=1)]
    for event in sorted(normalized, key=lambda item: (item["sequence"], item["event_id"])):
        record_id = event["operating_record_id"]
        current = projection.get(record_id) or _empty_record(event)
        _apply_event(current, event)
        projection[record_id] = current
    return projection


def build_operating_projection_report(data: dict[str, Any], report_id: str = "operating-projection") -> dict[str, Any]:
    """Build a report for operating event reduction and validation."""
    events = [event for event in data.get("events", []) if isinstance(event, dict)]
    normalized_events = [_normalize_event(event, sequence=index) for index, event in enumerate(events, start=1)]
    event_stream_findings = _event_stream_findings(normalized_events, strict=bool(data.get("verify_event_stream", False)))
    projection = reduce_operating_events(events)
    as_of_date = str(data.get("as_of_date") or "")
    _apply_time_based_transitions(projection, as_of_date=as_of_date)
    findings = [*event_stream_findings, *_projection_findings(projection)]
    records = sorted(projection.values(), key=lambda item: item["operating_record_id"])
    return {
        "schema_version": "HATE/v1",
        "record_type": "operating-projection-report",
        "report_id": report_id,
        "overall_status": "hold" if findings else "pass",
        "readiness_effect": "hold" if findings else "none",
        "events": sorted(normalized_events, key=lambda item: (item["sequence"], item["event_id"])),
        "records": records,
        "findings": findings,
        "summary": {
            "event_count": len(events),
            "record_count": len(records),
            "finding_count": len(findings),
            "event_stream_finding_count": len(event_stream_findings),
            "open_count": sum(1 for record in records if record["status"] == "open"),
            "accepted_count": sum(1 for record in records if record["status"] == "accepted"),
            "expired_count": sum(1 for record in records if record["status"] == "expired"),
            "as_of_date": as_of_date,
        },
        "sourceRefs": list(data.get("sourceRefs") or ["fixtures/platform/operations/operating-projection/fixture.json"]),
    }


def _normalize_event(raw: dict[str, Any], *, sequence: int) -> dict[str, Any]:
    event_type = str(raw.get("event_type") or "")
    entity_kind = str(raw.get("entity_kind") or "finding")
    return {
        "schema_version": str(raw.get("schema_version") or "HATE/v1"),
        "record_type": "operating-event-record",
        "event_id": str(raw.get("event_id") or f"event-{sequence:04d}"),
        "sequence": int(raw.get("sequence") or sequence),
        "event_type": event_type,
        "occurred_at": str(raw.get("occurred_at") or ""),
        "operating_record_id": str(raw.get("operating_record_id") or raw.get("entity_id") or f"operating-{sequence:04d}"),
        "entity_kind": entity_kind if entity_kind in VALID_ENTITY_KINDS else "finding",
        "entity_id": str(raw.get("entity_id") or raw.get("operating_record_id") or f"entity-{sequence:04d}"),
        "severity": str(raw.get("severity") or "medium"),
        "readiness_effect": str(raw.get("readiness_effect") or "none"),
        "owner": str(raw.get("owner") or ""),
        "due_date": str(raw.get("due_date") or ""),
        "expiry_date": str(raw.get("expiry_date") or ""),
        "justification": str(raw.get("justification") or ""),
        "decision_basis": list(raw.get("decision_basis") or []),
        "evidence_refs": list(raw.get("evidence_refs") or []),
        "superseding_record_id": str(raw.get("superseding_record_id") or ""),
        "actor": str(raw.get("actor") or ""),
        "reason": str(raw.get("reason") or ""),
        "reviewer": str(raw.get("reviewer") or ""),
        "required_decision": str(raw.get("required_decision") or ""),
        "decision_reason": str(raw.get("decision_reason") or ""),
        "blocking": bool(raw.get("blocking", False)),
        "external_system": str(raw.get("external_system") or ""),
        "external_ref": str(raw.get("external_ref") or ""),
        "external_status": str(raw.get("external_status") or ""),
        "sync_direction": str(raw.get("sync_direction") or raw.get("direction") or ""),
        "sync_status": str(raw.get("sync_status") or ""),
        "last_synced_at": str(raw.get("last_synced_at") or ""),
        "sync_error": str(raw.get("sync_error") or ""),
        "delivery_target": str(raw.get("delivery_target") or ""),
        "delivery_status": str(raw.get("delivery_status") or ""),
        "attempt": int(raw.get("attempt") or 0),
        "error_code": str(raw.get("error_code") or ""),
        "retention_policy_id": str(raw.get("retention_policy_id") or ""),
        "legal_hold_id": str(raw.get("legal_hold_id") or ""),
        "rebuild_id": str(raw.get("rebuild_id") or ""),
        "previous_event_hash": str(raw.get("previous_event_hash") or ""),
        "event_hash": str(raw.get("event_hash") or ""),
        "sourceRefs": list(raw.get("sourceRefs") or []),
    }


def _empty_record(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "HATE/v1",
        "record_type": "operating-finding-record",
        "operating_record_id": event["operating_record_id"],
        "entity_kind": event["entity_kind"],
        "entity_id": event["entity_id"],
        "status": "open",
        "severity": event["severity"],
        "readiness_effect": event["readiness_effect"],
        "owner": event["owner"],
        "due_date": event["due_date"],
        "expiry_date": event["expiry_date"],
        "sourceRefs": list(event["sourceRefs"]),
        "evidence_refs": list(event["evidence_refs"]),
        "decision_basis": list(event["decision_basis"]),
        "last_event_id": event["event_id"],
        "superseding_record_id": "",
        "merged_into_record_id": "",
        "tracker_syncs": [],
        "notifications": [],
        "retention_events": [],
        "legal_holds": [],
        "rebuild_events": [],
        "manual_review": {
            "reviewer": event["reviewer"],
            "required_decision": event["required_decision"],
            "decision_reason": event["decision_reason"],
            "blocking": event["blocking"],
        },
    }


def _apply_event(record: dict[str, Any], event: dict[str, Any]) -> None:
    record["last_event_id"] = event["event_id"]
    record["entity_kind"] = event["entity_kind"]
    record["entity_id"] = event["entity_id"]
    for key in ("severity", "readiness_effect", "owner", "due_date", "expiry_date"):
        if event.get(key):
            record[key] = event[key]
    record["sourceRefs"] = _dedupe([*record.get("sourceRefs", []), *event["sourceRefs"]])
    record["evidence_refs"] = _dedupe([*record.get("evidence_refs", []), *event["evidence_refs"]])
    record["decision_basis"] = _dedupe([*record.get("decision_basis", []), *event["decision_basis"]])
    if event["event_type"] in EVENT_STATUS:
        record["status"] = EVENT_STATUS[event["event_type"]]
    elif event["event_type"] in MIRROR_EVENT_TYPES:
        _apply_mirror_event(record, event)
    if event["event_type"] == "record_superseded":
        record["superseding_record_id"] = event["superseding_record_id"]
    if event["event_type"] == "finding_deduplicated":
        record["merged_into_record_id"] = event["superseding_record_id"]
    if event["event_type"] in {"manual_review_requested", "manual_review_decided"}:
        record["manual_review"] = {
            "reviewer": event["reviewer"],
            "required_decision": event["required_decision"],
            "decision_reason": event["decision_reason"] or event["reason"],
            "blocking": event["blocking"],
        }


def _apply_mirror_event(record: dict[str, Any], event: dict[str, Any]) -> None:
    if event["event_type"].startswith("tracker_sync"):
        record["tracker_syncs"].append(
            {
                "event_id": event["event_id"],
                "external_system": event["external_system"],
                "external_ref": event["external_ref"],
                "external_status": event["external_status"],
                "sync_direction": event["sync_direction"],
                "sync_status": event["sync_status"],
                "last_synced_at": event["last_synced_at"],
                "sync_error": event["sync_error"],
                "sourceRefs": list(event["sourceRefs"]),
            }
        )
    if event["event_type"].startswith("notification") or event["event_type"] == "sla_breach_detected":
        record["notifications"].append(
            {
                "event_id": event["event_id"],
                "event_type": event["event_type"],
                "delivery_target": event["delivery_target"],
                "delivery_status": event["delivery_status"],
                "attempt": event["attempt"],
                "error_code": event["error_code"],
                "sourceRefs": list(event["sourceRefs"]),
            }
        )
    if event["event_type"] == "retention_applied":
        record["retention_events"].append(
            {
                "event_id": event["event_id"],
                "retention_policy_id": event["retention_policy_id"],
                "sourceRefs": list(event["sourceRefs"]),
            }
        )
    if event["event_type"] == "legal_hold_applied":
        record["legal_holds"].append(
            {
                "event_id": event["event_id"],
                "legal_hold_id": event["legal_hold_id"],
                "sourceRefs": list(event["sourceRefs"]),
            }
        )
    if event["event_type"] == "projection_rebuilt":
        record["rebuild_events"].append(
            {
                "event_id": event["event_id"],
                "rebuild_id": event["rebuild_id"],
                "previous_event_hash": event["previous_event_hash"],
                "event_hash": event["event_hash"],
                "sourceRefs": list(event["sourceRefs"]),
            }
        )


def _apply_time_based_transitions(projection: dict[str, dict[str, Any]], *, as_of_date: str) -> None:
    if not as_of_date:
        return
    today = _parse_date(as_of_date)
    if today is None:
        return
    for record in projection.values():
        if record["status"] not in {"accepted", "open"}:
            continue
        expiry = _parse_date(record.get("expiry_date", ""))
        if expiry is not None and expiry < today and record["status"] == "accepted":
            record["status"] = "expired"
            record["readiness_effect"] = "hold"
        if expiry is not None and expiry < today and record["entity_kind"] == "manual_review" and record["status"] == "open":
            record["status"] = "expired"
            record["readiness_effect"] = "hold"


def _projection_findings(projection: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    findings = []
    for record in projection.values():
        if record["status"] == "accepted" and (not record["owner"] or not record["expiry_date"]):
            findings.append(_finding("operating_accepted_debt_missing_owner_or_expiry", record))
        if record["status"] == "accepted" and not record["decision_basis"]:
            findings.append(_finding("operating_accepted_debt_missing_decision_basis", record))
        if record["status"] == "open" and record["readiness_effect"] in {"hold", "hard_dq", "blocked"}:
            if not record["owner"] or not record["due_date"]:
                findings.append(_finding("operating_blocking_record_missing_owner_or_due_date", record))
        if record["status"] == "accepted" and record.get("expiry_date") and _parse_date(record["expiry_date"]) is None:
            findings.append(_finding("operating_accepted_debt_invalid_expiry", record))
        if record["status"] == "expired":
            findings.append(_finding("operating_accepted_debt_expired", record))
        if record["status"] == "resolved" and not record["evidence_refs"]:
            findings.append(_finding("operating_resolution_missing_evidence", record))
        if record["entity_kind"] == "manual_review" and record["status"] in {"open", "resolved"}:
            review = record.get("manual_review", {})
            if not record["owner"] or not record["expiry_date"]:
                findings.append(_finding("operating_manual_review_missing_owner_or_expiry", record))
            if not review.get("required_decision"):
                findings.append(_finding("operating_manual_review_missing_required_decision", record))
            if record["status"] == "resolved" and not record["evidence_refs"]:
                findings.append(_finding("operating_manual_review_decision_missing_evidence", record))
            if record["expiry_date"] and _parse_date(record["expiry_date"]) is None:
                findings.append(_finding("operating_manual_review_invalid_expiry", record))
        if record["entity_kind"] == "manual_review" and record["status"] == "expired":
            findings.append(_finding("operating_manual_review_expired", record))
        if record["status"] == "superseded" and not record["superseding_record_id"]:
            findings.append(_finding("operating_supersede_missing_target", record))
        if record["status"] == "superseded" and record["superseding_record_id"] and record["superseding_record_id"] not in projection:
            findings.append(_finding("operating_supersede_target_not_found", record))
        if record["status"] == "merged" and not record["merged_into_record_id"]:
            findings.append(_finding("operating_dedupe_missing_target", record))
        if record["status"] == "merged" and record["merged_into_record_id"] and record["merged_into_record_id"] not in projection:
            findings.append(_finding("operating_dedupe_target_not_found", record))
        if any(item["sync_direction"] == "inbound" and item["external_status"] in {"closed", "resolved"} for item in record["tracker_syncs"]):
            if record["status"] not in {"resolved", "revoked", "superseded", "merged"}:
                findings.append(_finding("operating_inbound_tracker_close_denied", record))
        if any(item["event_type"] == "notification_failed" for item in record["notifications"]):
            findings.append(_finding("operating_notification_failed", record))
        if any(item["event_type"] == "sla_breach_detected" for item in record["notifications"]):
            findings.append(_finding("operating_sla_breach_detected", record))
        if any(not item["rebuild_id"] for item in record["rebuild_events"]):
            findings.append(_finding("operating_projection_rebuild_missing_id", record))
        if record["rebuild_events"] and record["status"] in {"accepted", "expired"} and not record["expiry_date"]:
            findings.append(_finding("operating_projection_rebuild_lost_expiry", record))
        if any(not item["retention_policy_id"] for item in record["retention_events"]):
            findings.append(_finding("operating_retention_missing_policy", record))
        if any(not item["legal_hold_id"] for item in record["legal_holds"]):
            findings.append(_finding("operating_legal_hold_missing_id", record))
    return findings


def _event_stream_findings(events: list[dict[str, Any]], *, strict: bool) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    ordered = sorted(events, key=lambda item: (item["sequence"], item["event_id"]))
    previous_sequence = 0
    previous_hash = ""
    seen_ids: set[str] = set()
    for event in ordered:
        if event["event_id"] in seen_ids:
            findings.append(_event_finding("projection_rebuild_failed_duplicate_event_id", event))
        seen_ids.add(event["event_id"])
        if previous_sequence and event["sequence"] <= previous_sequence:
            findings.append(_event_finding("projection_rebuild_failed_non_monotonic_sequence", event))
        if strict and previous_sequence and event["sequence"] != previous_sequence + 1:
            findings.append(_event_finding("projection_rebuild_failed_event_gap", event))
        if strict and not event["actor"]:
            findings.append(_event_finding("projection_rebuild_failed_missing_actor", event))
        if strict and not event["occurred_at"]:
            findings.append(_event_finding("projection_rebuild_failed_missing_occurred_at", event))
        if event["previous_event_hash"] and previous_hash and event["previous_event_hash"] != previous_hash:
            findings.append(_event_finding("projection_rebuild_failed_hash_continuity", event))
        previous_sequence = event["sequence"]
        previous_hash = event["event_hash"] or previous_hash
    return findings


def _finding(code: str, record: dict[str, Any]) -> dict[str, Any]:
    return {
        "code": code,
        "severity": "high",
        "readiness_effect": "hold",
        "message": f"{code} for {record['operating_record_id']}",
        "operating_record_id": record["operating_record_id"],
    }


def _event_finding(code: str, event: dict[str, Any]) -> dict[str, Any]:
    return {
        "code": code,
        "severity": "high",
        "readiness_effect": "hold",
        "message": f"{code} for {event['event_id']}",
        "event_id": event["event_id"],
        "operating_record_id": event["operating_record_id"],
    }


def _dedupe(values: list[Any]) -> list[Any]:
    result = []
    seen = set()
    for value in values:
        marker = str(value)
        if marker not in seen and value not in (None, ""):
            seen.add(marker)
            result.append(value)
    return result


def _parse_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
