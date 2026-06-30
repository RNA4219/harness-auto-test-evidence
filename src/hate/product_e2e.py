"""Product E2E UAT journey evaluation for HATE-GAP-020."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


REQUIRED_EVIDENCE = {
    "product-e2e-uat-report.json",
    "journey-summary.md",
    "evidence-map.json",
    "open-risk-register.json",
}

JOURNEY_OWNERS = {
    "developer_pr_loop": "Developer",
    "qa_risk_review": "QA Lead",
    "release_review": "Release Manager",
    "admin_governance": "Platform Admin",
    "security_quarantine": "Security Engineer",
    "support_triage": "Support Engineer",
}

JOURNEY_REQUIRED_NEGATIVES = {
    "developer_pr_loop": "parser-failure",
    "qa_risk_review": "no-oracle",
    "release_review": "qeg-invalid",
    "admin_governance": "rbac-denied",
    "security_quarantine": "block",
    "support_triage": "raw-artifact-denied",
}

RBAC_JOURNEYS = {"admin_governance"}


@dataclass(frozen=True)
class ProductE2EFinding:
    code: str
    severity: str
    message: str
    sourceRef: str
    journey: str
    readiness_effect: str = "hold"

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "sourceRef": self.sourceRef,
            "journey": self.journey,
            "readiness_effect": self.readiness_effect,
        }


def evaluate_product_e2e_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_product_e2e_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "product-e2e-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_product_e2e_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "product-e2e-uat-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["product-e2e"])
    journeys = _normalize_journeys(input_data)
    findings: list[ProductE2EFinding] = []
    for journey in journeys:
        findings.extend(_findings_for_journey(journey, source_refs[0]))

    status = "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": "product-e2e-uat-report",
        "report_id": report_id,
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "journeys": journeys,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "journey_count": len(journeys),
            "finding_count": len(findings),
            "positive_journey_count": sum(1 for journey in journeys if journey["expected_path"] == "positive"),
            "negative_journey_count": sum(1 for journey in journeys if journey["expected_path"] == "negative"),
            "scope_safe": not findings,
        },
        "sourceRefs": sorted(set(source_refs)),
    }


def _normalize_journeys(input_data: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(input_data.get("journeys"), list):
        return [_normalize_journey(dict(item)) for item in input_data["journeys"]]
    return [_normalize_journey(dict(input_data))]


def _normalize_journey(data: dict[str, Any]) -> dict[str, Any]:
    journey = str(data.get("journey") or "unknown")
    emitted = set(data.get("emitted_evidence") or REQUIRED_EVIDENCE)
    owner = str(data.get("owner") or JOURNEY_OWNERS.get(journey, "Unassigned"))
    return {
        "journey": journey,
        "owner": owner,
        "expected_path": str(data.get("expected_path") or _expected_path(data)),
        "required_negative_case": JOURNEY_REQUIRED_NEGATIVES.get(journey, ""),
        "has_negative_case": bool(data.get("has_negative_case", True)),
        "rbac_negative_case": bool(data.get("rbac_negative_case", journey in RBAC_JOURNEYS)),
        "emitted_evidence": sorted(str(item) for item in emitted),
        "visual_evidence": bool(data.get("visual_evidence", True)),
        "precheck": data.get("precheck"),
        "parser_status": data.get("parser_status"),
        "risk_count": int(data.get("risk_count", 0)),
        "oracle_count": int(data.get("oracle_count", 0)),
        "manual_review_open": bool(data.get("manual_review_open", False)),
        "release_pack_status": data.get("release_pack_status"),
        "qeg_claim": data.get("qeg_claim"),
        "role": data.get("role"),
        "action": str(data.get("action") or ""),
        "audit_event": bool(data.get("audit_event", True)),
        "unsafe_artifact": bool(data.get("unsafe_artifact", False)),
        "summary_safe": bool(data.get("summary_safe", True)),
        "diagnostic_bundle": data.get("diagnostic_bundle"),
        "raw_artifact_export": bool(data.get("raw_artifact_export", False)),
        "exposes_secret": bool(data.get("exposes_secret", False)),
        "exposes_pii": bool(data.get("exposes_pii", False)),
        "exposes_customer_source": bool(data.get("exposes_customer_source", False)),
    }


def _expected_path(data: dict[str, Any]) -> str:
    negative_markers = [
        data.get("parser_status") == "failed",
        data.get("risk_count", 0) > data.get("oracle_count", 0),
        data.get("qeg_claim") == "approved",
        data.get("role") != "admin" and str(data.get("action") or "").startswith("update_"),
        bool(data.get("unsafe_artifact")) and not bool(data.get("summary_safe", True)),
        bool(data.get("raw_artifact_export")),
    ]
    return "negative" if any(negative_markers) else "positive"


def _findings_for_journey(journey: dict[str, Any], source_ref: str) -> list[ProductE2EFinding]:
    findings: list[ProductE2EFinding] = []
    name = journey["journey"]
    if name not in JOURNEY_OWNERS:
        findings.append(_finding("e2e_unknown_journey", f"Unknown product E2E journey: {name}", source_ref, name))
        return findings

    if journey["expected_path"] == "positive" and not journey["has_negative_case"]:
        findings.append(_finding(
            "e2e_happy_path_only",
            "Product E2E journey must include a negative counterpart.",
            source_ref,
            name,
        ))
    if name in RBAC_JOURNEYS and not journey["rbac_negative_case"]:
        findings.append(_finding(
            "e2e_rbac_negative_missing",
            "UI/API governance journey requires an RBAC negative case.",
            source_ref,
            name,
        ))
    findings.extend(_evidence_findings(journey, source_ref))
    findings.extend(_journey_specific_findings(journey, source_ref))
    return findings


def _evidence_findings(journey: dict[str, Any], source_ref: str) -> list[ProductE2EFinding]:
    findings: list[ProductE2EFinding] = []
    missing = sorted(REQUIRED_EVIDENCE - set(journey["emitted_evidence"]))
    if missing:
        findings.append(_finding(
            "e2e_required_evidence_missing",
            f"Product E2E evidence missing: {', '.join(missing)}",
            source_ref,
            journey["journey"],
        ))
    if not journey["visual_evidence"]:
        findings.append(_finding(
            "e2e_visual_evidence_missing",
            "UI-involved E2E journey requires screenshots or rendered report evidence.",
            source_ref,
            journey["journey"],
        ))
    return findings


def _journey_specific_findings(journey: dict[str, Any], source_ref: str) -> list[ProductE2EFinding]:
    name = journey["journey"]
    findings: list[ProductE2EFinding] = []
    if name == "developer_pr_loop" and journey["parser_status"] == "failed":
        findings.append(_finding("e2e_developer_parser_failure", "Developer PR loop parser failed.", source_ref, name))
    elif name == "qa_risk_review" and journey["risk_count"] > journey["oracle_count"]:
        findings.append(_finding("e2e_qa_risk_without_oracle", "QA risk review has risks without oracle evidence.", source_ref, name))
    elif name == "release_review" and journey["qeg_claim"] == "approved":
        findings.append(_finding("e2e_release_qeg_approval_overclaim", "Release journey must not claim QEG approval.", source_ref, name))
    elif name == "admin_governance" and journey["role"] != "admin" and journey["action"].startswith("update_"):
        findings.append(_finding("e2e_admin_rbac_denied", "Non-admin role attempted governance mutation.", source_ref, name))
    elif name == "security_quarantine" and journey["unsafe_artifact"] and not journey["summary_safe"]:
        findings.append(_finding("e2e_security_quarantine_block", "Unsafe artifact must stay quarantined.", source_ref, name))
    elif name == "support_triage" and journey["raw_artifact_export"]:
        findings.append(_finding("e2e_support_raw_artifact_denied", "Support triage must not export raw artifacts.", source_ref, name))

    if name == "admin_governance" and journey["role"] == "admin" and not journey["audit_event"]:
        findings.append(_finding("e2e_admin_audit_event_missing", "Admin governance mutation requires an audit event.", source_ref, name))
    if journey["exposes_secret"] or journey["exposes_pii"] or journey["exposes_customer_source"]:
        findings.append(_finding(
            "e2e_scope_safety_violation",
            "Product E2E evidence exposes secret, PII, customer source, or unsafe artifact.",
            source_ref,
            name,
        ))
    return findings


def _finding(code: str, message: str, source_ref: str, journey: str) -> ProductE2EFinding:
    return ProductE2EFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
        journey=journey,
    )
