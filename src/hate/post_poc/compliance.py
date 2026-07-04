from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .common import apply_productization_contract_tree, productization_envelope


CONTROL_CLAIM_CLASSES = {
    "data_flow",
    "subprocessor",
    "encryption",
    "retention",
    "residency",
    "access_control",
    "vulnerability_response",
    "incident_response",
}


@dataclass(frozen=True)
class ComplianceFinding:
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


def evaluate_compliance_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    report = build_compliance_report(
        payload.get("input", {}),
        report_id=str(payload.get("fixture_id") or "compliance-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_compliance_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "compliance-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["compliance"])
    claims = [_normalize_claim(item) for item in input_data.get("claims", [])]
    decisions = [_normalize_decision(item) for item in input_data.get("decisions", [])]
    export = _normalize_export(input_data.get("export", {}), claims)
    pack = _evidence_pack(input_data, claims, decisions, export)
    findings = _findings_for(claims, decisions, export, source_refs[0])
    status = "hold" if findings else "pass"
    report = {
        "schema_version": "HATE/v1",
        "record_type": "compliance-report",
        "report_id": report_id,
        **productization_envelope(input_data, report_id=report_id, source_refs=source_refs),
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "compliance_evidence_pack": pack,
        "procurement_questionnaire_export": export,
        "control_claims": claims,
        "review_decisions": decisions,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "claim_count": len(claims),
            "reviewed_claim_count": len({decision["control_id"] for decision in decisions if decision["review_status"] == "approved"}),
            "customer_safe_export": export["customer_safe_export"],
            "restricted_data_present": export["restricted_data_present"],
            "finding_count": len(findings),
        },
        "sourceRefs": sorted(set(source_refs)),
    }
    return apply_productization_contract_tree(report, source_refs=source_refs)


def _normalize_claim(raw: dict[str, Any]) -> dict[str, Any]:
    claim = dict(raw or {})
    return {
        "record_type": "control-claim-record",
        "control_id": str(claim.get("control_id") or ""),
        "claim_class": str(claim.get("claim_class") or ""),
        "claim_text": str(claim.get("claim_text") or ""),
        "evidence_refs": [str(item) for item in claim.get("evidence_refs", [])],
        "expires_at": str(claim.get("expires_at") or ""),
        "supported": bool(claim.get("supported", True)),
    }


def _normalize_decision(raw: dict[str, Any]) -> dict[str, Any]:
    decision = dict(raw or {})
    return {
        "record_type": "compliance-review-decision",
        "control_id": str(decision.get("control_id") or ""),
        "reviewer": str(decision.get("reviewer") or ""),
        "review_status": str(decision.get("review_status") or ""),
        "reviewed_at": str(decision.get("reviewed_at") or ""),
        "expires_at": str(decision.get("expires_at") or ""),
    }


def _normalize_export(raw: dict[str, Any], claims: list[dict[str, Any]]) -> dict[str, Any]:
    export = dict(raw or {})
    return {
        "record_type": "procurement-questionnaire-export",
        "export_id": str(export.get("export_id") or "procurement-export"),
        "customer_safe_export": bool(export.get("customer_safe_export", False)),
        "redaction_report_ref": str(export.get("redaction_report_ref") or ""),
        "restricted_data_present": bool(export.get("restricted_data_present", False)),
        "answered_control_ids": [str(item) for item in export.get("answered_control_ids", [claim["control_id"] for claim in claims])],
    }


def _evidence_pack(
    input_data: dict[str, Any],
    claims: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    export: dict[str, Any],
) -> dict[str, Any]:
    return {
        "record_type": "compliance-evidence-pack",
        "pack_id": str(input_data.get("pack_id") or "compliance-pack"),
        "control_ids": [claim["control_id"] for claim in claims],
        "reviewed_control_ids": [decision["control_id"] for decision in decisions if decision["review_status"] == "approved"],
        "customer_safe_export": export["customer_safe_export"],
        "redaction_report_ref": export["redaction_report_ref"],
    }


def _findings_for(
    claims: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    export: dict[str, Any],
    source_ref: str,
) -> list[ComplianceFinding]:
    findings: list[ComplianceFinding] = []
    decision_by_control = {decision["control_id"]: decision for decision in decisions}
    answered = set(export["answered_control_ids"])
    for claim in claims:
        if not claim["evidence_refs"] or claim["claim_class"] not in CONTROL_CLAIM_CLASSES:
            findings.append(_finding("compliance_control_evidence_missing", "Control claim is missing evidence or has unsupported claim_class.", source_ref))
        if not claim["supported"] or claim["control_id"] not in answered:
            findings.append(_finding("procurement_answer_unsupported", "Procurement answer is not supported by a control claim and evidence.", source_ref))
        if _is_stale(claim["expires_at"]):
            findings.append(_finding("compliance_claim_stale", "Control claim is stale or expired.", source_ref))
        decision = decision_by_control.get(claim["control_id"])
        if not decision or not decision["reviewer"] or decision["review_status"] != "approved":
            findings.append(_finding("compliance_reviewer_missing", "Control claim requires an approved reviewer decision.", source_ref))
        elif _is_stale(decision["expires_at"]):
            findings.append(_finding("compliance_claim_stale", "Compliance review decision is stale or expired.", source_ref))
    if export["customer_safe_export"] and (export["restricted_data_present"] or not export["redaction_report_ref"]):
        findings.append(_finding("compliance_export_contains_restricted_data", "Customer-safe export contains restricted data or lacks redaction report.", source_ref))
    return findings


def _is_stale(expires_at: str) -> bool:
    if not expires_at:
        return True
    try:
        expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError:
        return True
    now = datetime.fromisoformat("2026-07-03T00:00:00+00:00")
    return expiry <= now


def _finding(code: str, message: str, source_ref: str) -> ComplianceFinding:
    return ComplianceFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
        readiness_effect="hold",
    )
