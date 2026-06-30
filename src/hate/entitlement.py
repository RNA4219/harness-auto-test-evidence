"""Packaging and entitlement evaluator for HATE-GAP-004."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


EDITION_ORDER = {
    "local": 0,
    "oss-local": 0,
    "team": 1,
    "team_ga": 1,
    "enterprise": 2,
    "regulated": 3,
}

FEATURE_MIN_EDITION = {
    "local_precheck": "local",
    "p0a_golden_path": "local",
    "canonical_json": "local",
    "qeg_export": "local",
    "github_action_summary": "team",
    "adapter_registry": "team",
    "hosted_dashboard": "enterprise",
    "hosted_read_model": "enterprise",
    "org_workspace_model": "enterprise",
    "tenant_isolation_admin": "enterprise",
    "org_rbac": "enterprise",
    "audit_log": "enterprise",
    "retention_policy": "enterprise",
    "sso": "enterprise",
    "scim": "enterprise",
    "siem_connector": "enterprise",
    "private_artifact_storage": "regulated",
    "legal_hold": "regulated",
    "attestation_metadata": "regulated",
}

LOCAL_FIRST_FEATURES = {"local_precheck", "p0a_golden_path", "canonical_json", "qeg_export", "adapter_sdk"}


@dataclass
class EntitlementFinding:
    code: str
    severity: str
    message: str
    source_refs: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "source_refs": self.source_refs,
        }


@dataclass
class EntitlementDecision:
    plan: str
    feature: str
    mode: str
    required_edition: str
    status: str
    readiness_effect: str
    entitlement_status: str
    precheck_decision_override: bool
    qeg_verdict_override: bool
    over_limit: bool
    over_limit_action: str
    findings: list[EntitlementFinding]
    audit_event: dict[str, Any]

    def as_report(self, *, source_version: str, source_refs: list[str]) -> dict[str, Any]:
        report = {
            "schema_version": "HATE/v1",
            "record_type": "entitlement-report",
            "source_version": source_version,
            "status": self.status,
            "readiness_effect": self.readiness_effect,
            "plan": self.plan,
            "feature": self.feature,
            "mode": self.mode,
            "required_edition": self.required_edition,
            "entitlement_status": self.entitlement_status,
            "precheck_decision_override": self.precheck_decision_override,
            "qeg_verdict_override": self.qeg_verdict_override,
            "over_limit": self.over_limit,
            "over_limit_action": self.over_limit_action,
            "audit_events": [self.audit_event],
            "findings": [finding.as_dict() for finding in self.findings],
            "sourceRefs": source_refs,
        }
        if self.findings:
            report["finding_code"] = self.findings[0].code
        return report


def evaluate_entitlement_fixture(payload: dict[str, Any], *, source_version: str = "unknown") -> dict[str, Any]:
    data = payload.get("input", {})
    decision = evaluate_entitlement(data)
    return decision.as_report(source_version=source_version, source_refs=[str(payload.get("fixture_id") or "entitlement-fixture")])


def evaluate_entitlement(data: dict[str, Any]) -> EntitlementDecision:
    plan = _normalize_edition(str(data.get("plan") or data.get("edition") or "local"))
    feature = str(data.get("feature") or "local_precheck")
    mode = str(data.get("mode") or "local_first")
    required_edition = _normalize_edition(str(data.get("required_edition") or FEATURE_MIN_EDITION.get(feature, "enterprise")))
    over_limit = bool(data.get("over_limit")) or _usage_over_limit(data.get("usage"), data.get("limits"))
    precheck_override = bool(data.get("precheck_decision_override"))
    qeg_override = bool(data.get("qeg_verdict_override"))

    findings: list[EntitlementFinding] = []
    if _edition_level(plan) < _edition_level(required_edition):
        findings.append(_finding(
            "entitlement_feature_denied",
            "high",
            f"{feature} requires {required_edition} edition but current plan is {plan}",
        ))
    if feature in LOCAL_FIRST_FEATURES and mode == "local_first" and plan in {"local", "oss-local"}:
        findings = [item for item in findings if item.code != "entitlement_feature_denied"]
    if precheck_override:
        findings.append(_finding(
            "entitlement_precheck_override_denied",
            "critical",
            "entitlement must not override HATE precheck decisions",
        ))
    if qeg_override:
        findings.append(_finding(
            "entitlement_qeg_override_denied",
            "critical",
            "entitlement must not override QEG verdicts",
        ))

    status = "hold" if any(item.severity in {"high", "critical"} for item in findings) else "pass"
    readiness_effect = "hold" if status == "hold" else "none"
    entitlement_status = "denied" if any(item.code == "entitlement_feature_denied" for item in findings) else "available"
    if over_limit and not findings:
        entitlement_status = "over_limit_warning"
    over_limit_action = "warn_only_preserve_evidence" if over_limit else "within_limit"
    audit_event = _audit_event(
        plan=plan,
        feature=feature,
        mode=mode,
        required_edition=required_edition,
        status=status,
        finding_code=findings[0].code if findings else "",
        over_limit=over_limit,
        over_limit_action=over_limit_action,
    )
    return EntitlementDecision(
        plan=plan,
        feature=feature,
        mode=mode,
        required_edition=required_edition,
        status=status,
        readiness_effect=readiness_effect,
        entitlement_status=entitlement_status,
        precheck_decision_override=precheck_override,
        qeg_verdict_override=qeg_override,
        over_limit=over_limit,
        over_limit_action=over_limit_action,
        findings=findings,
        audit_event=audit_event,
    )


def _normalize_edition(value: str) -> str:
    normalized = value.lower().replace("-", "_")
    if normalized == "team_ga":
        return "team"
    if normalized == "oss_local":
        return "local"
    return normalized


def _edition_level(value: str) -> int:
    return EDITION_ORDER.get(_normalize_edition(value), 0)


def _usage_over_limit(usage: Any, limits: Any) -> bool:
    if not isinstance(usage, dict) or not isinstance(limits, dict):
        return False
    for meter, value in usage.items():
        limit = limits.get(meter)
        if limit is not None and value is not None and float(value) > float(limit):
            return True
    return False


def _finding(code: str, severity: str, message: str) -> EntitlementFinding:
    return EntitlementFinding(
        code=code,
        severity=severity,
        message=message,
        source_refs=["docs/process/PACKAGING_ENTITLEMENT_CONTRACT.md"],
    )


def _audit_event(
    *,
    plan: str,
    feature: str,
    mode: str,
    required_edition: str,
    status: str,
    finding_code: str,
    over_limit: bool,
    over_limit_action: str,
) -> dict[str, Any]:
    return {
        "event_type": "entitlement_decision",
        "plan": plan,
        "feature": feature,
        "mode": mode,
        "required_edition": required_edition,
        "decision": "allow" if status == "pass" else "deny",
        "finding_code": finding_code,
        "over_limit": over_limit,
        "over_limit_action": over_limit_action,
        "created_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
