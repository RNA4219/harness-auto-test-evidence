"""Security procurement helpers for HATE-GAP-046."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProcurementFinding:
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


def normalize_procurement_config(raw: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw or {})
    return {
        "security_review_packet": dict(config.get("security_review_packet", {}) or {}),
        "control_claims": _list_of_dicts(config.get("control_claims", [])),
        "vulnerability_slas": _list_of_dicts(config.get("vulnerability_slas", [])),
        "review_decisions": _list_of_dicts(config.get("review_decisions", [])),
        "export_manifest": dict(config.get("export_manifest", {}) or {}),
        "procurement_export_safe": bool(config.get("procurement_export_safe", False)),
        "raw_artifact_in_export": bool(config.get("raw_artifact_in_export", False)),
        "restricted_data_in_export": bool(config.get("restricted_data_in_export", False)),
    }


def procurement_summary(config: dict[str, Any]) -> dict[str, Any]:
    unsupported = [claim for claim in config["control_claims"] if claim.get("claim_class") == "unsupported"]
    overdue = [sla for sla in config["vulnerability_slas"] if sla.get("overdue")]
    return {
        "control_claim_count": len(config["control_claims"]),
        "unsupported_claim_count": len(unsupported),
        "vulnerability_sla_count": len(config["vulnerability_slas"]),
        "overdue_vulnerability_sla_count": len(overdue),
        "review_decision_count": len(config["review_decisions"]),
        "procurement_export_safe": config["procurement_export_safe"],
    }


def procurement_diagnostics(config: dict[str, Any]) -> dict[str, Any]:
    control_ids = [str(claim.get("claim_id") or "") for claim in config["control_claims"] if claim.get("claim_id")]
    reviewer_targets = {str(decision.get("target_ref") or "") for decision in config["review_decisions"] if decision.get("target_ref")}
    claims_missing_evidence = sorted(
        str(claim.get("claim_id") or "control-claim")
        for claim in config["control_claims"]
        if not claim.get("evidence_refs") or not claim.get("sourceRef")
    )
    stale_claims = sorted(
        str(claim.get("claim_id") or "control-claim")
        for claim in config["control_claims"]
        if claim.get("stale") or claim.get("evidence_freshness") == "stale"
    )
    claims_missing_reviewer = sorted(
        str(claim.get("claim_id") or "control-claim")
        for claim in config["control_claims"]
        if str(claim.get("claim_id") or "") not in reviewer_targets
    )
    slas_missing_owner_due = sorted(
        str(sla.get("sla_id") or sla.get("severity") or "vulnerability-sla")
        for sla in config["vulnerability_slas"]
        if not sla.get("owner") or not sla.get("due_date") or not sla.get("sourceRef")
    )
    export = config["export_manifest"]
    export_missing = not bool(export.get("manifest_id") and export.get("redaction_profile") and export.get("approved_evidence_refs"))
    unsafe_export = bool(
        config["raw_artifact_in_export"]
        or config["restricted_data_in_export"]
        or export.get("contains_raw_artifacts")
        or export.get("contains_restricted_data")
    )
    return {
        "duplicate_control_claims": sorted({item for item in control_ids if control_ids.count(item) > 1}),
        "claims_missing_evidence": claims_missing_evidence,
        "stale_control_claims": stale_claims,
        "claims_missing_reviewer_decision": claims_missing_reviewer,
        "vulnerability_slas_missing_owner_due": slas_missing_owner_due,
        "export_manifest_missing": export_missing,
        "unsafe_export_detected": unsafe_export,
        "review_decisions_without_source_ref": sorted(
            str(decision.get("decision_id") or "review-decision")
            for decision in config["review_decisions"]
            if not decision.get("sourceRef") or not decision.get("reviewer") or not decision.get("decision")
        ),
    }


def procurement_diagnostic_summary(diagnostics: dict[str, Any]) -> dict[str, Any]:
    return {
        "duplicate_control_claim_count": len(diagnostics["duplicate_control_claims"]),
        "claim_evidence_gap_count": len(diagnostics["claims_missing_evidence"]),
        "stale_control_claim_count": len(diagnostics["stale_control_claims"]),
        "claim_reviewer_gap_count": len(diagnostics["claims_missing_reviewer_decision"]),
        "vulnerability_sla_owner_due_gap_count": len(diagnostics["vulnerability_slas_missing_owner_due"]),
        "review_decision_source_gap_count": len(diagnostics["review_decisions_without_source_ref"]),
    }


def procurement_findings(
    config: dict[str, Any],
    diagnostics: dict[str, Any],
    source_ref: str,
) -> list[ProcurementFinding]:
    findings: list[ProcurementFinding] = []
    packet = config["security_review_packet"]
    missing_packet = [key for key in ("architecture", "data_flow", "data_classes", "subprocessors", "encryption", "secrets_handling", "retention_summary") if not packet.get(key)]
    if missing_packet:
        findings.append(_finding("security_procurement_packet_incomplete", f"Security review packet missing: {', '.join(missing_packet)}.", source_ref))
    for claim in config["control_claims"]:
        if claim.get("claim_class") == "unsupported":
            findings.append(_finding("security_procurement_unsupported_certification_claim", "Unsupported certification or control claim blocks product-ready.", source_ref))
    for sla in config["vulnerability_slas"]:
        if sla.get("severity") == "critical" and sla.get("overdue"):
            findings.append(_finding("security_procurement_overdue_critical_vulnerability", "Overdue critical vulnerability response blocks release pack.", source_ref))
    if not config["procurement_export_safe"] or diagnostics["unsafe_export_detected"]:
        findings.append(_finding("security_procurement_raw_artifact_export_denied", "Procurement export must contain only safe summaries and approved evidence refs.", source_ref))
    if diagnostics["duplicate_control_claims"]:
        findings.append(_finding("security_procurement_duplicate_control_claim", "Control claim ids must be stable and unique.", source_ref))
    if diagnostics["claims_missing_evidence"]:
        findings.append(_finding("security_procurement_control_evidence_missing", "Every control claim requires sourceRef and evidence refs.", source_ref))
    if diagnostics["stale_control_claims"]:
        findings.append(_finding("security_procurement_stale_control_claim", "Stale control claims require refresh or hold.", source_ref))
    if diagnostics["claims_missing_reviewer_decision"] or diagnostics["review_decisions_without_source_ref"]:
        findings.append(_finding("security_procurement_reviewer_missing", "Control claims require reviewer decision with sourceRef.", source_ref))
    if diagnostics["vulnerability_slas_missing_owner_due"]:
        findings.append(_finding("security_procurement_vulnerability_sla_incomplete", "Vulnerability SLA records require owner, due date, and sourceRef.", source_ref))
    if diagnostics["export_manifest_missing"]:
        findings.append(_finding("security_procurement_export_manifest_missing", "Procurement export requires manifest id, redaction profile, and approved evidence refs.", source_ref))
    return findings


def _finding(code: str, message: str, source_ref: str) -> ProcurementFinding:
    return ProcurementFinding(code=code, severity="high", message=message, sourceRef=source_ref)


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value if isinstance(item, dict)] if isinstance(value, list) else []
