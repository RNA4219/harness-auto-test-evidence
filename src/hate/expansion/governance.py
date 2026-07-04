"""Governance workflow helpers for HATE-GAP-045."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GovernanceFinding:
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


def normalize_governance_config(raw: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw or {})
    return {
        "policy_templates": _list_of_dicts(config.get("policy_templates", [])),
        "exception_requests": _list_of_dicts(config.get("exception_requests", [])),
        "delegations": _list_of_dicts(config.get("delegations", [])),
        "audit_events": _list_of_dicts(config.get("audit_events", [])),
        "review_packet": dict(config.get("review_packet", {}) or {}),
        "self_approval_detected": bool(config.get("self_approval_detected", False)),
        "service_account_approval_detected": bool(config.get("service_account_approval_detected", False)),
        "policy_diff_required": bool(config.get("policy_diff_required", True)),
    }


def governance_summary(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "policy_template_count": len(config["policy_templates"]),
        "exception_request_count": len(config["exception_requests"]),
        "delegation_count": len(config["delegations"]),
        "audit_event_count": len(config["audit_events"]),
        "expired_exception_count": int(config["review_packet"].get("expired_exception_count", 0) or 0),
        "unresolved_high_risk_debt_count": int(config["review_packet"].get("unresolved_high_risk_debt_count", 0) or 0),
    }


def governance_diagnostics(config: dict[str, Any]) -> dict[str, Any]:
    template_ids = [str(template.get("template_id") or "") for template in config["policy_templates"] if template.get("template_id")]
    exception_ids = [str(request.get("request_id") or "") for request in config["exception_requests"] if request.get("request_id")]
    audit_refs = {str(event.get("target_ref") or "") for event in config["audit_events"] if event.get("target_ref")}
    templates_missing_source_ref = sorted(
        str(template.get("template_id") or "policy-template")
        for template in config["policy_templates"]
        if not template.get("sourceRef")
    )
    templates_missing_diff_or_rollback = sorted(
        str(template.get("template_id") or "policy-template")
        for template in config["policy_templates"]
        if config["policy_diff_required"] and (not template.get("policy_diff_ref") or not template.get("rollback_plan_ref"))
    )
    templates_missing_separation = sorted(
        str(template.get("template_id") or "policy-template")
        for template in config["policy_templates"]
        if template.get("author") and template.get("author") == template.get("approver")
    )
    exceptions_missing_source_ref = sorted(
        str(request.get("request_id") or "exception-request")
        for request in config["exception_requests"]
        if not request.get("sourceRef")
    )
    exceptions_missing_risk_or_evidence = sorted(
        str(request.get("request_id") or "exception-request")
        for request in config["exception_requests"]
        if not request.get("affected_risks") or not request.get("compensating_evidence")
    )
    exceptions_missing_audit = sorted(
        str(request.get("request_id") or "exception-request")
        for request in config["exception_requests"]
        if str(request.get("request_id") or "") not in audit_refs
    )
    broad_exceptions = sorted(
        str(request.get("request_id") or "exception-request")
        for request in config["exception_requests"]
        if request.get("scope") in {"global", "all", "*"} or request.get("reviewer_decision") == "blanket_accept"
    )
    delegation_without_bounds = sorted(
        str(delegation.get("delegation_id") or "delegation")
        for delegation in config["delegations"]
        if not delegation.get("delegator") or not delegation.get("delegate") or not delegation.get("scope") or not delegation.get("expiry") or not delegation.get("sourceRef")
    )
    delegation_conflicts = sorted(
        str(delegation.get("delegation_id") or "delegation")
        for delegation in config["delegations"]
        if delegation.get("delegator") and delegation.get("delegator") == delegation.get("delegate")
    )
    return {
        "duplicate_policy_templates": sorted({item for item in template_ids if template_ids.count(item) > 1}),
        "duplicate_exception_requests": sorted({item for item in exception_ids if exception_ids.count(item) > 1}),
        "templates_missing_source_ref": templates_missing_source_ref,
        "templates_missing_diff_or_rollback": templates_missing_diff_or_rollback,
        "templates_missing_separation": templates_missing_separation,
        "exceptions_missing_source_ref": exceptions_missing_source_ref,
        "exceptions_missing_risk_or_evidence": exceptions_missing_risk_or_evidence,
        "exceptions_missing_audit_event": exceptions_missing_audit,
        "broad_exception_requests": broad_exceptions,
        "delegations_without_bounds": delegation_without_bounds,
        "delegation_conflicts": delegation_conflicts,
        "review_packet_missing_source_ref": not bool(config["review_packet"].get("sourceRef")),
    }


def governance_diagnostic_summary(diagnostics: dict[str, Any]) -> dict[str, Any]:
    return {
        "duplicate_policy_template_count": len(diagnostics["duplicate_policy_templates"]),
        "duplicate_exception_request_count": len(diagnostics["duplicate_exception_requests"]),
        "template_source_ref_gap_count": len(diagnostics["templates_missing_source_ref"]),
        "template_diff_or_rollback_gap_count": len(diagnostics["templates_missing_diff_or_rollback"]),
        "exception_source_ref_gap_count": len(diagnostics["exceptions_missing_source_ref"]),
        "exception_audit_gap_count": len(diagnostics["exceptions_missing_audit_event"]),
        "broad_exception_count": len(diagnostics["broad_exception_requests"]),
        "delegation_gap_count": len(diagnostics["delegations_without_bounds"]) + len(diagnostics["delegation_conflicts"]),
    }


def governance_findings(
    config: dict[str, Any],
    diagnostics: dict[str, Any],
    source_ref: str,
) -> list[GovernanceFinding]:
    findings: list[GovernanceFinding] = []
    for template in config["policy_templates"]:
        missing = [key for key in ("author", "approver", "effective_date", "review_cadence", "rollback_owner") if not template.get(key)]
        if missing:
            findings.append(_finding("governance_policy_template_incomplete", f"Policy template missing: {', '.join(missing)}.", source_ref))
    for request in config["exception_requests"]:
        missing = [key for key in ("owner", "expiry", "rationale", "affected_risks", "compensating_evidence", "reviewer_decision") if not request.get(key)]
        if missing:
            findings.append(_finding("governance_exception_request_incomplete", f"Exception request missing: {', '.join(missing)}.", source_ref))
    summary = governance_summary(config)
    if summary["expired_exception_count"] or summary["unresolved_high_risk_debt_count"]:
        findings.append(_finding("governance_review_packet_blockers_present", "Governance packet contains expired exceptions or unresolved high-risk debt.", source_ref))
    if config["self_approval_detected"] or diagnostics["templates_missing_separation"]:
        findings.append(_finding("governance_self_approval_denied", "Self-approval or service-account exception approval is denied.", source_ref))
    if config["service_account_approval_detected"]:
        findings.append(_finding("governance_service_account_approval_denied", "Service-account approval is denied.", source_ref))
    if diagnostics["duplicate_policy_templates"] or diagnostics["duplicate_exception_requests"]:
        findings.append(_finding("governance_duplicate_record", "Governance records must have stable unique ids.", source_ref))
    if diagnostics["templates_missing_source_ref"] or diagnostics["exceptions_missing_source_ref"] or diagnostics["review_packet_missing_source_ref"]:
        findings.append(_finding("governance_source_ref_missing", "Governance records require sourceRef.", source_ref))
    if diagnostics["templates_missing_diff_or_rollback"]:
        findings.append(_finding("governance_policy_diff_or_rollback_missing", "Policy templates require diff and rollback references.", source_ref))
    if diagnostics["exceptions_missing_risk_or_evidence"]:
        findings.append(_finding("governance_exception_risk_or_evidence_missing", "Exception requests require affected risks and compensating evidence.", source_ref))
    if diagnostics["exceptions_missing_audit_event"]:
        findings.append(_finding("governance_exception_audit_event_missing", "Accepted exceptions require append-only audit events.", source_ref))
    if diagnostics["broad_exception_requests"]:
        findings.append(_finding("governance_broad_exception_denied", "Global or blanket exception approval is denied.", source_ref))
    if diagnostics["delegations_without_bounds"] or diagnostics["delegation_conflicts"]:
        findings.append(_finding("governance_delegation_invalid", "Delegations require bounded scope, expiry, sourceRef, and separated actors.", source_ref))
    return findings


def _finding(code: str, message: str, source_ref: str) -> GovernanceFinding:
    return GovernanceFinding(code=code, severity="high", message=message, sourceRef=source_ref)


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value if isinstance(item, dict)] if isinstance(value, list) else []
