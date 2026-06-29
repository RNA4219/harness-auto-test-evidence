"""Commercial claim truthfulness gates.

Customer-facing claims are allowed only when they are backed by implemented
evidence records. Manual review may document an exception, but it cannot turn an
unsupported claim into implemented evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


CRITICAL_CLAIM_AREAS = {"enterprise", "security", "scale", "api", "ui", "release"}
IMPLEMENTED_STATUSES = {"implemented", "available", "supported"}
NON_IMPLEMENTED_STATUSES = {"planned", "candidate", "unsupported", "exception", "proposed"}


@dataclass
class CommercialClaimDecision:
    """Commercial truthfulness decision for one claim."""

    claim_id: str
    claim_text: str
    surface: str
    claim_area: str
    declared_status: str
    source_contract_refs: list[str]
    implementation_refs: list[str]
    required_evidence: list[str]
    observed_evidence: list[str]
    evidence_report_refs: list[str]
    sourceRefs: list[str]
    readiness_effect: str
    decision: str
    release_eligible: bool
    blocker_state: str
    procurement_response_text: str
    reason: str
    findings: list[dict[str, Any]] = field(default_factory=list)
    manual_review_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "claim_text": self.claim_text,
            "surface": self.surface,
            "claim_area": self.claim_area,
            "declared_status": self.declared_status,
            "source_contract_refs": self.source_contract_refs,
            "implementation_refs": self.implementation_refs,
            "required_evidence": self.required_evidence,
            "observed_evidence": self.observed_evidence,
            "evidence_report_refs": self.evidence_report_refs,
            "sourceRefs": self.sourceRefs,
            "readiness_effect": self.readiness_effect,
            "decision": self.decision,
            "release_eligible": self.release_eligible,
            "blocker_state": self.blocker_state,
            "procurement_response_text": self.procurement_response_text,
            "reason": self.reason,
            "findings": self.findings,
            "manual_review_refs": self.manual_review_refs,
        }


def evaluate_claim(
    claim: dict[str, Any],
    evidence_records: list[dict[str, Any]],
    *,
    profile: str = "release",
) -> CommercialClaimDecision:
    """Evaluate one commercial/procurement claim against observed evidence."""

    claim_id = str(claim.get("claim_id") or claim.get("id") or "")
    claim_text = str(claim.get("claim_text") or claim.get("text") or "")
    surface = str(claim.get("surface") or "unspecified")
    claim_area = str(claim.get("claim_area") or claim.get("area") or "general")
    declared_status = str(claim.get("declared_status") or claim.get("status") or "unsupported")
    source_contract_refs = [str(item) for item in claim.get("source_contract_refs") or claim.get("source_contracts") or []]
    implementation_refs = [str(item) for item in claim.get("implementation_refs") or claim.get("capability_refs") or []]
    required_evidence = [str(item) for item in claim.get("required_evidence", [])]
    source_refs = [str(item) for item in claim.get("sourceRefs") or claim.get("source_refs") or []]
    manual_review_refs = [str(item) for item in claim.get("manual_review_refs", [])]
    observed_evidence = _observed_evidence_ids(required_evidence, evidence_records)
    findings: list[dict[str, Any]] = []

    if not source_refs:
        findings.append(_finding("claim_missing_source_ref", "hold", "Commercial claim is missing sourceRefs.", claim_id, source_refs))

    if not source_contract_refs:
        findings.append(_finding(
            "claim_missing_source_contract_ref",
            "hold",
            "Commercial claim is missing source contract refs.",
            claim_id,
            source_refs,
        ))

    if declared_status in IMPLEMENTED_STATUSES and claim_area in CRITICAL_CLAIM_AREAS and not implementation_refs:
        findings.append(_finding(
            "implemented_claim_missing_implementation_ref",
            "hold",
            "Implemented critical claim is missing implementation refs.",
            claim_id,
            source_refs,
        ))

    if declared_status in NON_IMPLEMENTED_STATUSES and _wording_claims_available(claim_text, declared_status):
        findings.append(_finding(
            "planned_or_unsupported_claim_marked_available",
            _unsupported_effect(claim_area, profile),
            "Planned/unsupported capability is worded as available.",
            claim_id,
            source_refs,
        ))

    missing_evidence = [item for item in required_evidence if item not in observed_evidence]
    if declared_status in IMPLEMENTED_STATUSES and missing_evidence:
        findings.append(_finding(
            "implemented_claim_missing_evidence",
            _unsupported_effect(claim_area, profile),
            f"Implemented claim lacks evidence: {missing_evidence}.",
            claim_id,
            source_refs,
        ))

    if declared_status == "unsupported" and claim_area in CRITICAL_CLAIM_AREAS:
        findings.append(_finding(
            "unsupported_critical_claim",
            _unsupported_effect(claim_area, profile),
            "Unsupported critical claim cannot be customer-facing as available.",
            claim_id,
            source_refs,
        ))

    if claim.get("contradicts_release_pack"):
        findings.append(_finding(
            "claim_contradicts_release_pack",
            _unsupported_effect(claim_area, profile),
            "Commercial claim contradicts release candidate evidence.",
            claim_id,
            source_refs,
        ))

    if claim.get("requires_entitlement_note") and not claim.get("entitlement_note"):
        findings.append(_finding(
            "enterprise_entitlement_caveat_missing",
            "hold",
            "Enterprise claim requires an entitlement caveat.",
            claim_id,
            source_refs,
        ))

    if claim.get("manual_waiver_attempt") or (
        manual_review_refs and declared_status in {"unsupported", "planned", "candidate"} and _wording_claims_available(claim_text, declared_status)
    ):
        findings.append(_finding(
            "manual_review_cannot_waive_unsupported_claim",
            _unsupported_effect(claim_area, profile),
            "Manual review cannot auto-waive unsupported commercial claims.",
            claim_id,
            source_refs,
        ))

    readiness_effect = _max_effect(finding["readiness_effect"] for finding in findings)
    if not findings and declared_status in IMPLEMENTED_STATUSES:
        reason = "claim_supported_by_evidence"
    elif not findings:
        reason = "claim_truthfully_non_available"
    else:
        reason = findings[0]["code"]
    decision = "pass" if readiness_effect == "pass" else ("hold" if readiness_effect == "hold" else "blocked")
    release_eligible = readiness_effect == "pass" and declared_status in IMPLEMENTED_STATUSES
    return CommercialClaimDecision(
        claim_id=claim_id,
        claim_text=claim_text,
        surface=surface,
        claim_area=claim_area,
        declared_status=declared_status,
        source_contract_refs=source_contract_refs,
        implementation_refs=implementation_refs,
        required_evidence=required_evidence,
        observed_evidence=observed_evidence,
        evidence_report_refs=required_evidence,
        sourceRefs=source_refs,
        readiness_effect=readiness_effect,
        decision=decision,
        release_eligible=release_eligible,
        blocker_state="none" if readiness_effect == "pass" else readiness_effect,
        procurement_response_text=_procurement_response_text(claim_text, declared_status, release_eligible),
        reason=reason,
        findings=findings,
        manual_review_refs=manual_review_refs,
    )


def build_commercial_truthfulness_report(data: dict[str, Any]) -> dict[str, Any]:
    """Build commercial-truthfulness-report from claims and evidence records."""

    evidence_records = list(data.get("evidence_records") or [])
    decisions = [
        evaluate_claim(claim, evidence_records, profile=str(data.get("profile") or "release")).to_dict()
        for claim in data.get("claims", [])
    ]
    findings = [finding for decision in decisions for finding in decision.get("findings", [])]
    return {
        "schema_version": "HATE/v1",
        "record_type": "commercial-truthfulness-report",
        "report_id": data.get("report_id", "commercial-truthfulness-report"),
        "claims": decisions,
        "findings": findings,
        "summary": {
            "claim_count": len(decisions),
            "supported_claim_count": sum(1 for item in decisions if item["readiness_effect"] == "pass"),
            "release_eligible_claim_count": sum(1 for item in decisions if item["release_eligible"]),
            "hold_count": sum(1 for item in decisions if item["readiness_effect"] == "hold"),
            "hard_dq_count": sum(1 for item in decisions if item["readiness_effect"] == "hard_dq"),
            "unsupported_claim_count": sum(1 for item in decisions if item["declared_status"] == "unsupported"),
            "readiness_effect": _max_effect(item["readiness_effect"] for item in decisions),
        },
        "sourceRefs": sorted({ref for decision in decisions for ref in decision.get("sourceRefs", [])}),
    }


def _observed_evidence_ids(required_evidence: list[str], evidence_records: list[dict[str, Any]]) -> list[str]:
    observed: list[str] = []
    for required in required_evidence:
        for evidence in evidence_records:
            candidates = {
                str(evidence.get("evidence_id") or ""),
                str(evidence.get("report_type") or ""),
                str(evidence.get("record_type") or ""),
                str(evidence.get("artifact") or ""),
            }
            if required in candidates and evidence.get("status", "pass") in {"pass", "implemented", "available", "supported"}:
                observed.append(required)
                break
    return observed


def _wording_claims_available(claim_text: str, declared_status: str) -> bool:
    lowered = claim_text.lower()
    return declared_status in NON_IMPLEMENTED_STATUSES and any(
        phrase in lowered
        for phrase in [
            "available",
            "supported",
            "ready",
            "implemented",
            "provides",
            "includes",
            "guarantees",
        ]
    )


def _unsupported_effect(claim_area: str, profile: str) -> str:
    if profile in {"release", "regulated"} and claim_area in CRITICAL_CLAIM_AREAS:
        return "hard_dq"
    return "hold"


def _finding(code: str, effect: str, message: str, claim_id: str, source_refs: list[str]) -> dict[str, Any]:
    return {
        "code": code,
        "severity": "critical" if effect == "hard_dq" else "high",
        "readiness_effect": effect,
        "message": message,
        "claim_id": claim_id,
        "sourceRef": source_refs[0] if source_refs else "",
    }


def _procurement_response_text(claim_text: str, declared_status: str, release_eligible: bool) -> str:
    if release_eligible:
        return f"Implemented and evidence-backed: {claim_text}"
    if declared_status in {"planned", "candidate", "proposed"}:
        return f"Planned, not currently available: {claim_text}"
    if declared_status in {"unsupported", "exception", "expired"}:
        return f"Not available as a supported commitment: {claim_text}"
    return f"Not release-eligible until evidence is complete: {claim_text}"


def _max_effect(effects: Any) -> str:
    order = {"pass": 0, "soft_gap": 1, "hold": 2, "hard_dq": 3}
    return max(effects, key=lambda item: order.get(item, 0), default="pass")
