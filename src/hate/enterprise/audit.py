"""Enterprise audit projection for local HATE control events."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .rbac import RBACDecision


AUDITED_ACTIONS = {
    "read",
    "export",
    "review",
    "approve_review",
    "reject_review",
    "quarantine",
    "release_quarantine",
    "admin",
    "configure_policy",
    "manage_role",
    "delete_resource",
}


@dataclass
class AuditEvent:
    """Append-only audit projection event."""

    event_id: str
    actor: str
    action: str
    resource: dict[str, Any]
    decision: str
    reason: str
    timestamp: str
    sourceRefs: list[str] = field(default_factory=list)
    previous_hash: str = ""
    event_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "actor": self.actor,
            "action": self.action,
            "resource": self.resource,
            "decision": self.decision,
            "reason": self.reason,
            "timestamp": self.timestamp,
            "sourceRefs": self.sourceRefs,
            "previous_hash": self.previous_hash,
            "event_hash": self.event_hash,
        }


def build_audit_event(
    decision: RBACDecision | dict[str, Any],
    timestamp: str | None = None,
    previous_hash: str = "",
) -> AuditEvent:
    """Build a deterministic audit event from an RBAC decision."""

    decision_dict = decision.to_dict() if isinstance(decision, RBACDecision) else dict(decision)
    timestamp = timestamp or datetime.now(UTC).replace(microsecond=0).isoformat()
    resource = decision_dict.get("resource") or {
        "type": decision_dict.get("resource_type", ""),
        "id": decision_dict.get("resource_id", ""),
        "classification": decision_dict.get("classification", "public"),
        "quarantine_status": decision_dict.get("quarantine_status", "none"),
    }
    base = {
        "actor": decision_dict.get("actor_id") or decision_dict.get("actor", ""),
        "action": decision_dict.get("action", ""),
        "resource": resource,
        "decision": decision_dict.get("decision", ""),
        "reason": decision_dict.get("reason", ""),
        "timestamp": timestamp,
        "sourceRefs": decision_dict.get("sourceRefs", []),
        "previous_hash": previous_hash,
    }
    event_hash = _stable_hash(base)
    event_id = f"audit-{event_hash[:16]}"
    return AuditEvent(
        event_id=event_id,
        actor=str(base["actor"]),
        action=str(base["action"]),
        resource=dict(resource),
        decision=str(base["decision"]),
        reason=str(base["reason"]),
        timestamp=timestamp,
        sourceRefs=list(base["sourceRefs"]),
        previous_hash=previous_hash,
        event_hash=event_hash,
    )


def validate_audit_events(
    events: list[AuditEvent | dict[str, Any]],
    required_decisions: list[RBACDecision | dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate audit event completeness and hash-chain integrity."""

    event_dicts = [event.to_dict() if isinstance(event, AuditEvent) else dict(event) for event in events]
    required = [
        decision.to_dict() if isinstance(decision, RBACDecision) else dict(decision)
        for decision in (required_decisions or [])
    ]

    findings: list[dict[str, Any]] = []
    for index, event in enumerate(event_dicts):
        missing = [
            field
            for field in ["actor", "action", "resource", "decision", "reason", "sourceRefs", "timestamp"]
            if not event.get(field)
        ]
        if missing:
            findings.append({
                "code": "audit_event_missing_required_field",
                "severity": "high",
                "message": f"Audit event {event.get('event_id', index)} is missing {', '.join(missing)}.",
                "sourceRef": _first_source_ref(event),
            })
        expected_hash = _event_hash_without_id(event)
        if event.get("event_hash") and expected_hash != event.get("event_hash"):
            findings.append({
                "code": "audit_hash_chain_broken",
                "severity": "high",
                "message": f"Audit event {event.get('event_id', index)} hash does not match payload.",
                "sourceRef": _first_source_ref(event),
            })

    for decision in required:
        if decision.get("action") not in AUDITED_ACTIONS:
            continue
        if not _has_matching_event(decision, event_dicts):
            findings.append({
                "code": "missing_audit_event",
                "severity": "high",
                "message": f"Missing audit event for {decision.get('action')} on {decision.get('resource_id')}.",
                "sourceRef": _first_source_ref(decision),
            })

    readiness_effect = "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": "enterprise-audit-validation",
        "readiness_effect": readiness_effect,
        "findings": findings,
        "summary": {
            "event_count": len(event_dicts),
            "required_decision_count": len(required),
            "finding_count": len(findings),
        },
    }


def build_enterprise_control_report(
    decisions: list[RBACDecision | dict[str, Any]],
    audit_events: list[AuditEvent | dict[str, Any]],
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    """Build the enterprise-control-report RBAC/audit projection section."""

    decision_dicts = [decision.to_dict() if isinstance(decision, RBACDecision) else dict(decision) for decision in decisions]
    event_dicts = [event.to_dict() if isinstance(event, AuditEvent) else dict(event) for event in audit_events]
    validation = validate_audit_events(event_dicts, decision_dicts)
    source_refs = list(source_refs or [])
    if not source_refs:
        for decision in decision_dicts:
            source_refs.extend(decision.get("sourceRefs", []))
    return {
        "schema_version": "HATE/v1",
        "record_type": "enterprise-control-report",
        "connector_dry_runs": [],
        "rbac_decisions": decision_dicts,
        "audit_events": event_dicts,
        "findings": validation["findings"],
        "summary": {
            "rbac_decision_count": len(decision_dicts),
            "audit_event_count": len(event_dicts),
            "denied_count": sum(1 for item in decision_dicts if item.get("decision") == "denied"),
            "hold_count": 1 if validation["readiness_effect"] == "hold" else 0,
            "readiness_effect": validation["readiness_effect"],
        },
        "sourceRefs": sorted(set(source_refs)),
    }


def _has_matching_event(decision: dict[str, Any], events: list[dict[str, Any]]) -> bool:
    for event in events:
        resource = event.get("resource", {})
        if (
            event.get("actor") == (decision.get("actor_id") or decision.get("actor"))
            and event.get("action") == decision.get("action")
            and resource.get("type") == decision.get("resource_type")
            and resource.get("id") == decision.get("resource_id")
            and event.get("decision") == decision.get("decision")
            and event.get("reason") == decision.get("reason")
        ):
            return True
    return False


def _event_hash_without_id(event: dict[str, Any]) -> str:
    return _stable_hash({
        "actor": event.get("actor", ""),
        "action": event.get("action", ""),
        "resource": event.get("resource", {}),
        "decision": event.get("decision", ""),
        "reason": event.get("reason", ""),
        "timestamp": event.get("timestamp", ""),
        "sourceRefs": event.get("sourceRefs", []),
        "previous_hash": event.get("previous_hash", ""),
    })


def _stable_hash(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _first_source_ref(value: dict[str, Any]) -> str:
    refs = value.get("sourceRefs") or []
    if refs:
        return str(refs[0])
    return ""
