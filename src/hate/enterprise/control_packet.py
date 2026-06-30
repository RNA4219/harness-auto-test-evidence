"""Enterprise control packet evaluation for HATE-GAP-015."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .audit import build_audit_event, build_enterprise_control_report
from .rbac import evaluate_rbac


WRITE_ACTIONS = {
    "update_retention_policy",
    "configure_policy",
    "manage_role",
    "delete_resource",
    "release_quarantine",
}

ACTION_ALIASES = {
    "update_retention_policy": "configure_policy",
    "update_rbac_policy": "manage_role",
}


@dataclass(frozen=True)
class EnterpriseControlFinding:
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


def evaluate_enterprise_control_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_enterprise_control_packet_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "enterprise-control-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_enterprise_control_packet_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "enterprise-control-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["enterprise-control-packet"])
    decisions = []
    audit_events = []
    findings: list[EnterpriseControlFinding] = []

    for packet in _normalize_packets(input_data):
        packet_findings = _packet_findings(packet, source_refs[0])
        findings.extend(packet_findings)
        decision = _decision_for(packet, source_refs)
        decisions.append(decision)
        audit_events.append(build_audit_event(decision, packet.get("timestamp") or "2026-06-30T00:00:00+00:00").to_dict())
        if decision["decision"] == "denied" and not packet_findings:
            findings.append(_finding_for_denial(packet, decision, source_refs[0]))

    base_report = build_enterprise_control_report(decisions, audit_events, source_refs)
    findings.extend(
        EnterpriseControlFinding(
            code=str(item.get("code")),
            severity=str(item.get("severity", "high")),
            message=str(item.get("message", "")),
            sourceRef=str(item.get("sourceRef") or source_refs[0]),
        )
        for item in base_report.get("findings", [])
    )
    status = "hold" if findings else "pass"

    base_report.update({
        "report_id": report_id,
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "control_packets": [_public_packet(packet) for packet in _normalize_packets(input_data)],
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            **base_report.get("summary", {}),
            "packet_count": len(_normalize_packets(input_data)),
            "finding_count": len(findings),
            "readiness_effect": "hold" if findings else "pass",
        },
    })
    return base_report


def _normalize_packets(input_data: dict[str, Any]) -> list[dict[str, Any]]:
    raw_packets = input_data.get("control_packets")
    if isinstance(raw_packets, list):
        return [_normalize_packet(packet) for packet in raw_packets if isinstance(packet, dict)]
    raw_packet = input_data.get("control_packet")
    if isinstance(raw_packet, dict):
        return [_normalize_packet(raw_packet)]
    return [_normalize_packet(input_data)]


def _normalize_packet(raw: dict[str, Any]) -> dict[str, Any]:
    role = str(raw.get("role") or "viewer")
    action = str(raw.get("action") or "read")
    resource_type = str(raw.get("resource_type") or _resource_type_for(action))
    return {
        "actor_id": str(raw.get("actor_id") or raw.get("actor") or f"{role}-user"),
        "role": role,
        "action": action,
        "normalized_action": ACTION_ALIASES.get(action, action),
        "resource_type": resource_type,
        "resource_id": str(raw.get("resource_id") or f"{resource_type}-default"),
        "classification": str(raw.get("classification") or "internal"),
        "quarantine_status": str(raw.get("quarantine_status") or "none"),
        "access_level": str(raw.get("access_level") or "safe_metadata"),
        "timestamp": str(raw.get("timestamp") or "2026-06-30T00:00:00+00:00"),
        "requires_audit": bool(raw.get("requires_audit", True)),
    }


def _packet_findings(packet: dict[str, Any], source_ref: str) -> list[EnterpriseControlFinding]:
    if packet["role"] == "auditor" and packet["action"] in WRITE_ACTIONS:
        return [EnterpriseControlFinding(
            code="enterprise_auditor_write_denied",
            severity="high",
            message="Auditor role is read-only and cannot perform enterprise write controls.",
            sourceRef=source_ref,
        )]
    if packet["role"] == "service_account" and packet["action"] in {"approve_review", "reject_review"}:
        return [EnterpriseControlFinding(
            code="enterprise_service_account_human_approval_denied",
            severity="high",
            message="Service accounts cannot replace human approval decisions.",
            sourceRef=source_ref,
        )]
    return []


def _decision_for(packet: dict[str, Any], source_refs: list[str]) -> dict[str, Any]:
    actor = {
        "actor_id": packet["actor_id"],
        "role": packet["role"],
        "scopes": ["safe_metadata"],
        "sourceRefs": source_refs,
    }
    request = {
        "action": packet["normalized_action"],
        "resource_type": packet["resource_type"],
        "resource_id": packet["resource_id"],
        "classification": packet["classification"],
        "quarantine_status": packet["quarantine_status"],
        "access_level": packet["access_level"],
        "sourceRefs": source_refs,
    }
    return evaluate_rbac(actor, request, source_refs).to_dict()


def _finding_for_denial(
    packet: dict[str, Any],
    decision: dict[str, Any],
    source_ref: str,
) -> EnterpriseControlFinding:
    code = "enterprise_control_denied"
    if decision.get("reason") == "admin_permission_required":
        code = "enterprise_admin_permission_required"
    elif decision.get("reason") == "role_permission_denied":
        code = "enterprise_role_permission_denied"
    elif decision.get("reason") == "classification_scope_denied":
        code = "enterprise_classification_scope_denied"
    return EnterpriseControlFinding(
        code=code,
        severity="high",
        message=f"{packet['role']} cannot perform {packet['action']} on {packet['resource_type']}.",
        sourceRef=source_ref,
    )


def _resource_type_for(action: str) -> str:
    if action in {"update_retention_policy", "configure_policy", "update_rbac_policy", "manage_role"}:
        return "admin"
    if action in {"export"}:
        return "export"
    if action in {"approve_review", "reject_review", "review"}:
        return "manual_review"
    return "report"


def _public_packet(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "actor_id": packet["actor_id"],
        "role": packet["role"],
        "action": packet["action"],
        "normalized_action": packet["normalized_action"],
        "resource_type": packet["resource_type"],
        "resource_id": packet["resource_id"],
        "requires_audit": packet["requires_audit"],
    }
