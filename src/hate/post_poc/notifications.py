from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .common import apply_productization_contract_tree, productization_envelope


DELIVERY_TARGETS = {
    "slack_channel",
    "slack_dm",
    "email",
    "github_comment",
    "github_check_annotation",
    "webhook",
}

PASS_STATUSES = {"delivered"}
HOLD_STATUSES = {"failed", "retry_scheduled", "dead_lettered"}


@dataclass(frozen=True)
class NotificationFinding:
    code: str
    severity: str
    message: str
    sourceRef: str
    readiness_effect: str = "hold"

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "sourceRef": self.sourceRef,
            "readiness_effect": self.readiness_effect,
        }


def evaluate_notification_delivery_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_notification_delivery_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "notification-delivery-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_notification_delivery_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "notification-delivery-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["notification-delivery"])
    plan = _normalize_plan(input_data.get("plan", input_data))
    attempts = [_normalize_attempt(attempt) for attempt in input_data.get("attempts", [])]
    delivery_plan, delivery_attempts, dead_letters, audit_events, findings = _reduce_attempts(
        plan,
        attempts,
        source_refs[0],
    )
    status = "hold" if findings else "pass"
    report = {
        "schema_version": "HATE/v1",
        "record_type": "notification-delivery-report",
        "report_id": report_id,
        **productization_envelope(input_data, report_id=report_id, source_refs=source_refs),
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "delivery_plan": delivery_plan,
        "delivery_attempts": delivery_attempts,
        "dead_letter_events": dead_letters,
        "audit_events": audit_events,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "attempt_count": len(delivery_attempts),
            "dead_letter_count": len(dead_letters),
            "audit_event_count": len(audit_events),
            "finding_count": len(findings),
            "final_delivery_status": delivery_plan["delivery_status"],
            "operating_record_status_after": delivery_plan["operating_record_status_after"],
        },
        "sourceRefs": sorted(set(source_refs)),
    }
    return apply_productization_contract_tree(report, source_refs=source_refs)


def build_notification_routing_plan(
    input_data: dict[str, Any],
    *,
    plan_id: str = "notification-routing-plan",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["notification-routing"])
    incident = _normalize_operating_record(input_data.get("operating_record", input_data))
    subscribers = [_normalize_subscriber(item) for item in input_data.get("subscribers", [])]
    routing_entries = _routing_entries_for(incident, subscribers)
    findings = _routing_findings(incident, subscribers, routing_entries, source_refs[0])
    plan = {
        "schema_version": "HATE/v1",
        "record_type": "notification-routing-plan",
        "plan_id": plan_id,
        **productization_envelope(input_data, report_id=plan_id, source_refs=source_refs),
        "readiness_effect": "hold" if findings else "none",
        "operating_record": incident,
        "subscribers": subscribers,
        "routing_entries": routing_entries,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "subscriber_count": len(subscribers),
            "routing_entry_count": len(routing_entries),
            "primary_count": sum(1 for entry in routing_entries if entry["routing_role"] == "primary"),
            "escalation_count": sum(1 for entry in routing_entries if entry["routing_role"] == "escalation"),
            "hold_count": len(findings),
            "sla_breached": incident["sla_breached"],
        },
        "sourceRefs": sorted(set(source_refs)),
    }
    return apply_productization_contract_tree(plan, source_refs=source_refs)


def write_notification_routing_manifest(plan: dict[str, Any], out_path: str | Path) -> dict[str, Any]:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": "HATE/v1",
        "record_type": "notification-routing-manifest",
        "plan_id": str(plan.get("plan_id") or ""),
        **productization_envelope(plan, report_id=str(plan.get("plan_id") or "notification-routing-manifest"), source_refs=list(plan.get("sourceRefs", []))),
        "readiness_effect": str(plan.get("readiness_effect") or "none"),
        "operating_record_id": str(plan.get("operating_record", {}).get("operating_record_id") or ""),
        "routing_entries": list(plan.get("routing_entries", [])),
        "sourceRefs": list(plan.get("sourceRefs", [])),
    }
    apply_productization_contract_tree(manifest, source_refs=manifest["sourceRefs"])
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return {
        "schema_version": "HATE/v1",
        "record_type": "notification-routing-manifest-artifact",
        **productization_envelope(manifest, report_id=f"{manifest['plan_id']}:artifact", source_refs=manifest["sourceRefs"]),
        "readiness_effect": manifest["readiness_effect"],
        "artifact_path": str(path),
        "routing_entry_count": len(manifest["routing_entries"]),
        "sourceRefs": manifest["sourceRefs"],
    }


def _normalize_operating_record(raw: dict[str, Any]) -> dict[str, Any]:
    record = dict(raw or {})
    return {
        "record_type": "notification-operating-record",
        "operating_record_id": str(record.get("operating_record_id") or record.get("record_id") or ""),
        "severity": str(record.get("severity") or "medium"),
        "owner": str(record.get("owner") or ""),
        "team": str(record.get("team") or ""),
        "due_at": str(record.get("due_at") or ""),
        "sla_breached": bool(record.get("sla_breached", False)),
        "payload_hash": str(record.get("payload_hash") or ""),
        "redaction_report_ref": str(record.get("redaction_report_ref") or ""),
        "sourceRef": str(record.get("sourceRef") or record.get("operating_record_id") or "operating-record"),
    }


def _normalize_subscriber(raw: dict[str, Any]) -> dict[str, Any]:
    subscriber = dict(raw or {})
    return {
        "record_type": "notification-subscriber",
        "subscriber_id": str(subscriber.get("subscriber_id") or ""),
        "owner": str(subscriber.get("owner") or ""),
        "team": str(subscriber.get("team") or ""),
        "delivery_target": str(subscriber.get("delivery_target") or ""),
        "target_ref": str(subscriber.get("target_ref") or ""),
        "routing_role": str(subscriber.get("routing_role") or "primary"),
        "active": bool(subscriber.get("active", True)),
        "sourceRef": str(subscriber.get("sourceRef") or subscriber.get("subscriber_id") or "subscriber"),
    }


def _routing_entries_for(record: dict[str, Any], subscribers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for subscriber in subscribers:
        if not subscriber["active"]:
            continue
        owner_match = bool(record["owner"] and subscriber["owner"] == record["owner"])
        team_match = bool(record["team"] and subscriber["team"] == record["team"])
        escalation = subscriber["routing_role"] == "escalation" and record["sla_breached"]
        if not (owner_match or team_match or escalation):
            continue
        routing_role = "escalation" if escalation else "primary"
        entries.append({
            "record_type": "notification-routing-entry",
            "operating_record_id": record["operating_record_id"],
            "subscriber_id": subscriber["subscriber_id"],
            "routing_role": routing_role,
            "delivery_target": subscriber["delivery_target"],
            "target_ref": subscriber["target_ref"],
            "dedupe_key": f"{record['operating_record_id']}:{subscriber['subscriber_id']}:{routing_role}",
            "payload_hash": record["payload_hash"],
            "redaction_report_ref": record["redaction_report_ref"],
            "sourceRefs": [record["sourceRef"], subscriber["sourceRef"]],
        })
    return entries


def _routing_findings(
    record: dict[str, Any],
    subscribers: list[dict[str, Any]],
    entries: list[dict[str, Any]],
    source_ref: str,
) -> list[NotificationFinding]:
    findings: list[NotificationFinding] = []
    if not record["operating_record_id"] or not record["owner"]:
        findings.append(_finding("notification_owner_missing", "Operating record requires owner before notification routing.", source_ref))
    if not record["payload_hash"] or not record["redaction_report_ref"]:
        findings.append(_finding("notification_payload_unsafe", "Routing plan requires payload_hash and redaction_report_ref.", source_ref))
    if not entries:
        findings.append(_finding("notification_target_missing", "Routing plan requires at least one active owner/team subscriber.", source_ref))
    for entry in entries:
        if entry["delivery_target"] not in DELIVERY_TARGETS or not entry["target_ref"]:
            findings.append(_finding("notification_target_missing", "Routing entry has unsupported delivery target or missing target_ref.", source_ref))
    if record["sla_breached"] and not any(entry["routing_role"] == "escalation" for entry in entries):
        findings.append(_finding("notification_escalation_target_missing", "SLA-breached operating record requires escalation routing.", source_ref))
    if subscribers and not any(subscriber["active"] for subscriber in subscribers):
        findings.append(_finding("notification_target_missing", "All notification subscribers are inactive.", source_ref))
    return findings


def _normalize_plan(raw: dict[str, Any]) -> dict[str, Any]:
    plan = dict(raw or {})
    return {
        "record_type": "notification-delivery-plan",
        "notification_id": str(plan.get("notification_id") or ""),
        "operating_record_id": str(plan.get("operating_record_id") or ""),
        "delivery_target": str(plan.get("delivery_target") or ""),
        "target_ref": str(plan.get("target_ref") or ""),
        "dedupe_key": str(plan.get("dedupe_key") or ""),
        "payload_hash": str(plan.get("payload_hash") or ""),
        "payload_safe": bool(plan.get("payload_safe", True)),
        "redaction_report_ref": str(plan.get("redaction_report_ref") or ""),
        "signature_ref": str(plan.get("signature_ref") or ""),
        "attempt": int(plan.get("attempt") or 0),
        "max_attempts": int(plan.get("max_attempts") or 1),
        "next_retry_at": str(plan.get("next_retry_at") or ""),
        "delivery_status": str(plan.get("delivery_status") or "planned"),
        "error_code": str(plan.get("error_code") or ""),
        "operating_record_status_before": str(plan.get("operating_record_status_before") or "open"),
        "operating_record_status_after": str(plan.get("operating_record_status_after") or "open"),
    }


def _normalize_attempt(raw: dict[str, Any]) -> dict[str, Any]:
    attempt = dict(raw or {})
    return {
        "event_type": str(attempt.get("event_type") or "attempt"),
        "attempt": int(attempt.get("attempt") or 1),
        "delivery_status": str(attempt.get("delivery_status") or ""),
        "error_code": str(attempt.get("error_code") or ""),
        "next_retry_at": str(attempt.get("next_retry_at") or ""),
        "signature_ref": str(attempt.get("signature_ref") or ""),
        "redaction_report_ref": str(attempt.get("redaction_report_ref") or ""),
        "payload_hash": str(attempt.get("payload_hash") or ""),
        "dedupe_key": str(attempt.get("dedupe_key") or ""),
        "sourceRefs": [str(item) for item in attempt.get("sourceRefs", [])],
    }


def _reduce_attempts(
    plan: dict[str, Any],
    attempts: list[dict[str, Any]],
    source_ref: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[NotificationFinding]]:
    state = dict(plan)
    delivery_attempts: list[dict[str, Any]] = []
    dead_letters: list[dict[str, Any]] = []
    audit_events: list[dict[str, Any]] = []
    findings: list[NotificationFinding] = []

    _validate_plan(state, source_ref, findings)

    for index, attempt in enumerate(attempts):
        attempt_ref = attempt["sourceRefs"][0] if attempt["sourceRefs"] else f"{source_ref}#/attempts/{index}"
        _merge_attempt(state, attempt)
        event_type = attempt["event_type"]

        if event_type == "duplicate_suppressed":
            findings.append(_finding(
                "notification_duplicate_suppressed",
                "Duplicate notification was suppressed and retained as an audit event.",
                attempt_ref,
            ))
            state["delivery_status"] = "duplicate_suppressed"
            audit_events.append(_audit_event(state, event_type, attempt_ref))
            continue

        delivery_attempts.append(_attempt_record(state, attempt_ref))
        if state["delivery_status"] in HOLD_STATUSES:
            findings.append(_finding(
                "notification_delivery_failed",
                "Notification delivery failed and must not close the operating record.",
                attempt_ref,
            ))
        if state["delivery_status"] == "dead_lettered" or event_type == "dead_lettered":
            findings.append(_finding(
                "notification_dead_lettered",
                "Notification reached dead-letter state.",
                attempt_ref,
            ))
            dead_letters.append(_dead_letter_event(state, attempt_ref))
        if state["delivery_status"] == "retry_scheduled" and not state["next_retry_at"]:
            findings.append(_finding(
                "notification_delivery_failed",
                "Retry-scheduled notification requires next_retry_at.",
                attempt_ref,
            ))
        audit_events.append(_audit_event(state, event_type, attempt_ref))

    if state["delivery_status"] in HOLD_STATUSES:
        state["operating_record_status_after"] = state["operating_record_status_before"]

    return state, delivery_attempts, dead_letters, audit_events, findings


def _validate_plan(plan: dict[str, Any], source_ref: str, findings: list[NotificationFinding]) -> None:
    if plan["delivery_target"] not in DELIVERY_TARGETS or not plan["target_ref"]:
        findings.append(_finding(
            "notification_target_missing",
            "Notification delivery requires a supported delivery_target and target_ref.",
            source_ref,
        ))
    if not plan["payload_safe"] or not plan["redaction_report_ref"]:
        findings.append(_finding(
            "notification_payload_unsafe",
            "Notification payload requires redaction evidence and must not include unsafe body content.",
            source_ref,
        ))
    if plan["delivery_target"] == "webhook" and not plan["signature_ref"]:
        findings.append(_finding(
            "notification_signature_missing",
            "Webhook notification requires signature_ref.",
            source_ref,
        ))
    if not plan["dedupe_key"] or not plan["payload_hash"]:
        findings.append(_finding(
            "notification_target_missing",
            "Notification delivery requires dedupe_key and payload_hash.",
            source_ref,
        ))


def _merge_attempt(state: dict[str, Any], attempt: dict[str, Any]) -> None:
    for key in [
        "delivery_status",
        "error_code",
        "next_retry_at",
        "signature_ref",
        "redaction_report_ref",
        "payload_hash",
        "dedupe_key",
    ]:
        if attempt[key]:
            state[key] = attempt[key]
    state["attempt"] = attempt["attempt"] or state["attempt"]


def _attempt_record(state: dict[str, Any], source_ref: str) -> dict[str, Any]:
    return {
        "record_type": "notification-delivery-attempt",
        "notification_id": state["notification_id"],
        "operating_record_id": state["operating_record_id"],
        "delivery_target": state["delivery_target"],
        "target_ref": state["target_ref"],
        "dedupe_key": state["dedupe_key"],
        "payload_hash": state["payload_hash"],
        "attempt": state["attempt"],
        "max_attempts": state["max_attempts"],
        "next_retry_at": state["next_retry_at"],
        "delivery_status": state["delivery_status"],
        "error_code": state["error_code"],
        "signature_ref": state["signature_ref"],
        "redaction_report_ref": state["redaction_report_ref"],
        "sourceRefs": [source_ref],
    }


def _dead_letter_event(state: dict[str, Any], source_ref: str) -> dict[str, Any]:
    return {
        "record_type": "notification-dead-letter-event",
        "notification_id": state["notification_id"],
        "operating_record_id": state["operating_record_id"],
        "delivery_target": state["delivery_target"],
        "target_ref": state["target_ref"],
        "attempt": state["attempt"],
        "max_attempts": state["max_attempts"],
        "error_code": state["error_code"],
        "sourceRefs": [source_ref],
    }


def _audit_event(state: dict[str, Any], event_type: str, source_ref: str) -> dict[str, Any]:
    return {
        "record_type": "notification-audit-event",
        "notification_id": state["notification_id"],
        "operating_record_id": state["operating_record_id"],
        "event_type": event_type,
        "delivery_status": state["delivery_status"],
        "sourceRefs": [source_ref],
    }


def _finding(code: str, message: str, source_ref: str) -> NotificationFinding:
    return NotificationFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
        readiness_effect="hold",
    )
