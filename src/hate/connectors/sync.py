"""Platform connector sync payload evaluation.

Connector sync is a mirror boundary: outbound payloads are safe summaries, and
inbound acknowledgements cannot mutate canonical operating records.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any


REQUIRED_FIELDS = {
    "sync_id",
    "operating_record_id",
    "connector_id",
    "external_system",
    "direction",
    "operation",
    "idempotency_key",
    "payload_hash",
    "redaction_status",
    "sourceRefs",
}
VALID_DIRECTIONS = {"outbound", "inbound_ack"}
VALID_OPERATIONS = {"create", "update", "comment", "close", "ack"}
VALID_STATES = {
    "queued",
    "prepared",
    "sent",
    "acknowledged",
    "failed_retryable",
    "failed_terminal",
    "cancelled",
}
UNSAFE_PAYLOAD_KEYS = {
    "raw_artifact",
    "raw_artifact_body",
    "raw_artifact_content",
    "raw_artifact_path",
    "secret",
    "token",
    "password",
    "private_key",
    "pii",
}
INBOUND_FORBIDDEN_FIELDS = {"owner", "expiry_date", "due_date", "status", "lifecycle_state", "decision", "hidden"}


def build_connector_sync_report(data: dict[str, Any], report_id: str = "platform-connector-sync") -> dict[str, Any]:
    """Evaluate connector sync payloads against platform sync rules."""
    payloads = [_normalize_payload(item) for item in data.get("sync_payloads", []) if isinstance(item, dict)]
    findings: list[dict[str, Any]] = []
    accepted_payloads: list[dict[str, Any]] = []
    denied_payloads: list[dict[str, Any]] = []
    skipped_duplicates: list[dict[str, Any]] = []
    generated_events: list[dict[str, Any]] = []
    seen_idempotency: dict[str, str] = {}

    for payload in payloads:
        previous_hash = seen_idempotency.get(payload["idempotency_key"])
        if previous_hash and previous_hash == payload["payload_hash"]:
            skipped_duplicates.append(payload)
            generated_events.extend(_events_for_payload(payload, []))
            continue
        payload_findings = _payload_findings(payload, seen_idempotency)
        seen_idempotency[payload["idempotency_key"]] = payload["payload_hash"]
        if payload_findings:
            findings.extend(payload_findings)
            denied_payloads.append(payload)
        else:
            accepted_payloads.append(payload)
        generated_events.extend(_events_for_payload(payload, payload_findings))

    status = "hold" if findings else "pass"
    source_refs = _report_source_refs(data, payloads, generated_events, findings)
    return {
        "schema_version": "HATE/v1",
        "record_type": "platform-connector-sync-report",
        "report_id": report_id,
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "sync_payloads": payloads,
        "accepted_payloads": accepted_payloads,
        "denied_payloads": denied_payloads,
        "skipped_duplicate_payloads": skipped_duplicates,
        "generated_operating_events": generated_events,
        "findings": findings,
        "summary": {
            "payload_count": len(payloads),
            "accepted_count": len(accepted_payloads),
            "denied_count": len(denied_payloads),
            "skipped_duplicate_count": len(skipped_duplicates),
            "finding_count": len(findings),
            "generated_event_count": len(generated_events),
        },
        "sourceRefs": source_refs or ["fixtures/platform/connectors/connector-sync/fixture.json"],
    }


def _normalize_payload(raw: dict[str, Any]) -> dict[str, Any]:
    payload = dict(raw)
    payload["sourceRefs"] = list(raw.get("sourceRefs") or [])
    payload["payload"] = dict(raw.get("payload") or {})
    payload["state"] = str(raw.get("state") or "queued")
    for key in REQUIRED_FIELDS - {"sourceRefs"}:
        payload[key] = str(raw.get(key) or "")
    if not payload["payload_hash"] and payload["payload"]:
        payload["payload_hash"] = _payload_hash(payload["payload"])
    payload["safe_summary"] = _safe_summary(payload["payload"])
    return payload


def _payload_findings(payload: dict[str, Any], seen_idempotency: dict[str, str]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    missing = sorted(field for field in REQUIRED_FIELDS if not payload.get(field))
    if missing:
        findings.append(_finding("connector_sync_required_field_missing", payload, {"missing_fields": missing}))
    if payload["direction"] not in VALID_DIRECTIONS:
        findings.append(_finding("connector_sync_invalid_direction", payload))
    if payload["operation"] not in VALID_OPERATIONS:
        findings.append(_finding("connector_sync_invalid_operation", payload))
    if payload["state"] not in VALID_STATES:
        findings.append(_finding("connector_sync_invalid_state", payload))
    if payload["idempotency_key"] in seen_idempotency:
        findings.append(_finding("connector_sync_idempotency_key_reused_with_different_payload", payload))
    expected_hash = _payload_hash(payload["payload"])
    if payload["payload"] and payload["payload_hash"] != expected_hash:
        findings.append(_finding("connector_sync_payload_hash_mismatch", payload, {"expected_hash": expected_hash}))
    if payload["redaction_status"] not in {"not_required", "redacted"}:
        findings.append(_finding("connector_sync_redaction_not_safe", payload))
    if _contains_unsafe_payload(payload["payload"]):
        findings.append(_finding("connector_sync_unsafe_payload_denied", payload))
    if payload["direction"] == "inbound_ack":
        forbidden = sorted(field for field in INBOUND_FORBIDDEN_FIELDS if field in payload["payload"])
        if forbidden:
            findings.append(_finding("connector_sync_inbound_ack_mutation_denied", payload, {"forbidden_fields": forbidden}))
    if payload["state"] == "failed_terminal" and payload["operation"] == "close":
        findings.append(_finding("connector_sync_external_close_failure_non_canonical", payload))
    return findings


def _events_for_payload(payload: dict[str, Any], findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    event_type = "tracker_sync_completed" if not findings else "tracker_sync_failed"
    if payload["connector_id"].startswith("slack") or payload["external_system"] == "slack":
        event_type = "notification_sent" if not findings else "notification_failed"
    if payload["state"].startswith("failed"):
        event_type = "notification_failed" if payload["connector_id"].startswith("slack") or payload["external_system"] == "slack" else "tracker_sync_failed"
    if payload["direction"] == "inbound_ack" and not findings:
        event_type = "tracker_sync_completed"
    return [
        {
            "schema_version": "HATE/v1",
            "record_type": "operating-event-record",
            "event_id": f"sync-event-{payload['sync_id'] or 'missing'}",
            "sequence": 1,
            "event_type": event_type,
            "operating_record_id": payload["operating_record_id"],
            "entity_kind": "finding",
            "entity_id": payload["operating_record_id"],
            "external_system": payload["external_system"],
            "external_ref": str(payload["payload"].get("external_ref") or payload["payload"].get("external_url") or ""),
            "external_status": str(payload["payload"].get("external_status") or payload["state"]),
            "sync_direction": payload["direction"],
            "sync_status": payload["state"],
            "sync_error": ";".join(finding["code"] for finding in findings),
            "sourceRefs": list(payload["sourceRefs"]),
        }
    ]


def _finding(code: str, payload: dict[str, Any], extra: dict[str, Any] | None = None) -> dict[str, Any]:
    finding = {
        "code": code,
        "severity": "high",
        "readiness_effect": "hold",
        "message": f"{code} for {payload.get('sync_id') or 'missing-sync-id'}",
        "sync_id": payload.get("sync_id", ""),
        "operating_record_id": payload.get("operating_record_id", ""),
        "sourceRefs": list(payload.get("sourceRefs") or []),
    }
    if extra:
        finding.update(extra)
    return finding


def _payload_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _safe_summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if key not in UNSAFE_PAYLOAD_KEYS and not _looks_sensitive(str(value))
    }


def _contains_unsafe_payload(payload: dict[str, Any]) -> bool:
    if any(key in UNSAFE_PAYLOAD_KEYS for key in payload):
        return True
    return _looks_sensitive(json.dumps(payload, sort_keys=True))


def _looks_sensitive(value: str) -> bool:
    patterns = [
        r"(?i)(secret|password|token|private[_-]?key)\s*[:=]",
        r"(?i)bearer\s+[a-z0-9._-]{8,}",
        r"(?i)https?://[^\\s]+(token|signature|x-amz-signature)=",
        r"[A-Z]:\\\\Users\\\\[^\\s]+",
        r"/home/[^\\s]+",
    ]
    return any(re.search(pattern, value) for pattern in patterns)


def _report_source_refs(
    data: dict[str, Any],
    payloads: list[dict[str, Any]],
    events: list[dict[str, Any]],
    findings: list[dict[str, Any]],
) -> list[str]:
    refs: list[str] = []
    for item in [data, *payloads, *events, *findings]:
        refs.extend(_source_refs(item))
    return sorted(set(refs))


def _source_refs(item: Any) -> list[str]:
    if not isinstance(item, dict):
        return []
    refs: list[str] = []
    raw = item.get("sourceRefs")
    if isinstance(raw, list):
        refs.extend(str(ref) for ref in raw if str(ref))
    elif isinstance(raw, str) and raw:
        refs.append(raw)
    raw_ref = item.get("sourceRef")
    if isinstance(raw_ref, str) and raw_ref:
        refs.append(raw_ref)
    return refs
