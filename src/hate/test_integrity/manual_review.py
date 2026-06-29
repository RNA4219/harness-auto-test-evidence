"""Manual review request handler - HATE-PG-004C.

This module handles manual review requests for:
- Suspicious AI avoidance code patterns
- Fixture name coupling
- Broad mocks requiring human judgment
- Missing oracle for high-risk features
- Unsupported claims in evidence
- Missing/expired human records

Per PRODUCT_GRADE_IMPLEMENTATION_SPEC.md Section 6:
- Human records MUST have: owner, expiry, decision
- Expired human records = debt
- Manual review required for flagged integrity findings
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .coupling import (
    CouplingClassification,
    ManualReviewClassification,
    DETECTOR_ID_MANUAL_REVIEW,
)
from .models import IntegrityFinding, IntegrityRiskDebt


# Required decision types for manual review - per schema enum
REQUIRED_DECISION_TYPES = {
    "approve_or_reject",
    "verify_coverage_or_accept_risk",
    "verify_coupling_or_remove_branch",
    "verify_behavior_or_accept_weakness",
    "accept_weak_oracle_or_request_stronger",
    "accept_coverage_or_request_test",
    "fix_finding_or_accept_suppression",
    "verify_coupling_acceptable",
    "add_oracle_or_accept_risk",
    "add_oracle_or_accept_coverage_only",
    "verify_oracle_sufficiency",
    "verify_human_record_or_create",
    "extend_expiry_or_close",
}


@dataclass(frozen=True)
class HumanRecord:
    """Human record for tracking manual decisions."""
    __test__ = False

    record_id: str
    owner: str
    decision: str
    expiry: str
    created_at: str
    source_refs: list[str]
    justification: str | None
    status: str
    evidence_ref: str | None
    blocking: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "owner": self.owner,
            "decision": self.decision,
            "expiry": self.expiry,
            "created_at": self.created_at,
            "source_refs": self.source_refs,
            "justification": self.justification,
            "status": self.status,
            "evidence_ref": self.evidence_ref,
            "blocking": self.blocking,
        }

    def is_expired(self, now: str) -> bool:
        """Check if the record is expired."""
        if not self.expiry:
            return False
        return now > self.expiry


def classify_manual_review_requirement(
    finding: dict[str, Any],
    human_records: list[dict[str, Any]],
    now: str,
) -> ManualReviewClassification:
    """Classify if manual review is required for a finding.

    Returns the classification of manual review requirement:
    - SUSPICIOUS_AI_AVOIDANCE: AI avoidance patterns requiring review
    - FIXTURE_NAME_COUPLING: Fixture coupling requiring review
    - BROAD_MOCKS: Broad mocks requiring judgment
    - MISSING_ORACLE: Missing oracle for required feature
    - UNSUPPORTED_CLAIM: Unsupported claim requiring evidence
    - MISSING_HUMAN_RECORD: Finding requires human record but none exists
    - EXPIRED_HUMAN_RECORD: Human record expired, needs renewal
    - VALID_MANUAL_REVIEW: Valid human record exists
    """
    evidence_class = finding.get("evidence_class", "")

    # Check for existing valid human record
    for record in human_records:
        record_ref = record.get("evidence_ref", record.get("record_id", ""))
        finding_ref = finding.get("finding_id", "")
        if record_ref == finding_ref:
            expiry = record.get("expiry", "")
            if expiry and now > expiry:
                return ManualReviewClassification.EXPIRED_HUMAN_RECORD
            return ManualReviewClassification.VALID_MANUAL_REVIEW

    # Check evidence class for specific review types
    if evidence_class == "implementation_test_coupling":
        classification = finding.get("classification", "")
        if classification in {
            CouplingClassification.TEST_NAME_BRANCH.value,
            CouplingClassification.FIXTURE_NAME_BRANCH.value,
        }:
            return ManualReviewClassification.FIXTURE_NAME_COUPLING
        return ManualReviewClassification.SUSPICIOUS_AI_AVOIDANCE

    if evidence_class == "mock_abuse_detected":
        return ManualReviewClassification.BROAD_MOCKS

    if evidence_class == "risk_without_oracle":
        return ManualReviewClassification.MISSING_ORACLE

    if evidence_class == "coverage_without_evidence":
        return ManualReviewClassification.UNSUPPORTED_CLAIM

    if evidence_class == "assertion_quality":
        return ManualReviewClassification.MISSING_ORACLE

    # Check if manual review is flagged in finding
    if finding.get("manual_review_required"):
        return ManualReviewClassification.MISSING_HUMAN_RECORD

    return ManualReviewClassification.MISSING_HUMAN_RECORD


def generate_manual_review_request(
    finding: dict[str, Any],
    classification: ManualReviewClassification,
    *,
    fixture_id: str = "manual-review",
    now: str | None = None,
) -> dict[str, Any] | None:
    """Generate manual review request for a finding.

    Returns None if finding has valid manual review.
    Returns request dict if manual review required.
    """
    if classification == ManualReviewClassification.VALID_MANUAL_REVIEW:
        return None

    current_time = now or datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    finding_id = finding.get("finding_id", "")
    evidence_class = finding.get("evidence_class", "")
    severity = finding.get("severity", "medium")
    reason = finding.get("reason", "")
    source_refs = finding.get("sourceRefs", [])

    # Determine required decision type
    required_decision = finding.get("required_human_decision", "fix_finding_or_accept_suppression")
    if required_decision not in REQUIRED_DECISION_TYPES:
        required_decision = "fix_finding_or_accept_suppression"

    # Determine if blocking
    # Per HATE-PG-004C Issue 4: MISSING_HUMAN_RECORD and EXPIRED_HUMAN_RECORD must be blocking
    # to prevent auto-approval. All human record issues require explicit human decision.
    blocking = severity in ("high", "critical") or classification in {
        ManualReviewClassification.FIXTURE_NAME_COUPLING,
        ManualReviewClassification.MISSING_ORACLE,
        ManualReviewClassification.MISSING_HUMAN_RECORD,
        ManualReviewClassification.EXPIRED_HUMAN_RECORD,
    }

    # Generate justification text
    justification_text = {
        ManualReviewClassification.SUSPICIOUS_AI_AVOIDANCE: (
            "Suspicious AI avoidance code pattern detected. "
            "Production code appears to branch on test/fixture names, "
            "suggesting test-driven behavior modification."
        ),
        ManualReviewClassification.FIXTURE_NAME_COUPLING: (
            "Production code branches on fixture or test names. "
            "This coupling suggests production behavior changes based on test environment."
        ),
        ManualReviewClassification.BROAD_MOCKS: (
            "Broad mock usage detected. "
            "Over-mocking may hide actual integration issues."
        ),
        ManualReviewClassification.MISSING_ORACLE: (
            "High/critical risk feature lacks meaningful oracle. "
            "Expected value, contract, property, or mutation oracle required."
        ),
        ManualReviewClassification.UNSUPPORTED_CLAIM: (
            "Evidence claim lacks supporting oracle or test. "
            "Coverage alone is not sufficient evidence for required features."
        ),
        ManualReviewClassification.MISSING_HUMAN_RECORD: (
            "Finding flagged for manual review but no human record exists. "
            "Human decision required to resolve."
        ),
        ManualReviewClassification.EXPIRED_HUMAN_RECORD: (
            "Existing human record has expired. "
            "Review and renewal required."
        ),
    }

    justification = justification_text.get(
        classification,
        f"Manual review required for {evidence_class} finding."
    )

    request_id = f"{fixture_id}.request.{finding_id.replace('finding', '')}"
    if request_id.count(".") < 2:
        request_id = f"{fixture_id}.request.{finding_id}"

    # Default expiry: 30 days from now
    default_expiry = finding.get("expiry")
    if not default_expiry:
        from datetime import timedelta
        try:
            current_dt = datetime.fromisoformat(current_time.replace("Z", "+00:00"))
            default_expiry = (current_dt + timedelta(days=30)).isoformat().replace("+00:00", "Z")
        except (ValueError, TypeError):
            default_expiry = current_time

    return {
        "request_id": request_id,
        "risk_id": finding.get("risk_matrix_entry_ref") or finding_id,
        "owner": finding.get("owner") or "",
        "expiry_date": default_expiry,
        "expiry": default_expiry,
        "created_at": current_time,
        "source_refs": source_refs if source_refs else [finding_id],
        "status": "pending",
        "justification": justification,
        "evidence_context": [evidence_class, finding_id],
        "reason": reason or "Manual review required",
        "blocking": blocking,
        "required_decision": required_decision,
        "classification": classification.value,
        "sourceRef": source_refs[0] if source_refs else finding_id,
    }


def process_manual_review_requests(
    findings: list[dict[str, Any]],
    human_records: list[dict[str, Any]],
    *,
    fixture_id: str = "manual-review",
    profile: str = "default",
    now: str | None = None,
) -> dict[str, Any]:
    """Process all findings and generate manual review requests.

    Returns a manual review request document with:
    - summary: overall status
    - requests: list of manual review requests
    - findings: all findings reviewed
    - sourceRefs: aggregated source refs
    """
    current_time = now or datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    requests: list[dict[str, Any]] = []
    reviewed_findings: list[dict[str, Any]] = []
    all_refs: set[str] = set()

    for finding in findings:
        classification = classify_manual_review_requirement(finding, human_records, current_time)

        reviewed_finding = {
            **finding,
            "manual_review_classification": classification.value,
        }
        reviewed_findings.append(reviewed_finding)

        for ref in finding.get("sourceRefs", []):
            all_refs.add(ref)

        request = generate_manual_review_request(
            finding,
            classification,
            fixture_id=fixture_id,
            now=current_time,
        )
        if request:
            requests.append(request)
            for ref in request.get("source_refs", []):
                all_refs.add(ref)

    # Count by classification
    classification_counts: dict[str, int] = {}
    for rf in reviewed_findings:
        cls = rf.get("manual_review_classification", "unknown")
        classification_counts[cls] = classification_counts.get(cls, 0) + 1

    # Determine overall status - schema enum: ready, pending, blocked
    pending_count = sum(1 for r in requests if r.get("status") == "pending")
    blocking_count = sum(1 for r in requests if r.get("blocking"))
    valid_count = classification_counts.get(ManualReviewClassification.VALID_MANUAL_REVIEW.value, 0)

    # Count missing owner and expired
    missing_owner_count = sum(1 for r in requests if not r.get("owner"))
    expired_count = sum(
        1 for r in requests
        if r.get("classification") == ManualReviewClassification.EXPIRED_HUMAN_RECORD.value
    )
    hard_dq_count = sum(
        1 for r in requests
        if r.get("required_decision") == "fix_finding_or_accept_suppression"
    )

    if blocking_count > 0:
        overall_status = "blocked"
    elif pending_count > 0:
        overall_status = "pending"
    else:
        overall_status = "ready"

    summary = {
        "overall_status": overall_status,
        "request_count": len(requests),
        "pending_count": pending_count,
        "hard_dq_count": hard_dq_count,
        "missing_owner_count": missing_owner_count,
        "expired_count": expired_count,
        "finding_count": len(reviewed_findings),
        "blocking_count": blocking_count,
        "valid_count": valid_count,
        "classification_counts": classification_counts,
        "profile_effect": profile,
    }

    return {
        "schema_version": "HATE/v1",
        "record_type": "manual_review_request_bundle",
        "fixture_id": fixture_id,
        "profile": profile,
        "summary": summary,
        "requests": sorted(requests, key=lambda x: (x.get("blocking", False), x.get("request_id", ""))),
        "findings": [
            {
                "code": f.get("evidence_class", "unknown"),
                "severity": f.get("severity", "medium"),
                "message": f.get("reason", f.get("manual_review_classification", "Manual review required")),
                "sourceRef": f.get("sourceRefs", [f.get("finding_id", "")])[0] if f.get("sourceRefs") else f.get("finding_id", ""),
            }
            for f in sorted(reviewed_findings, key=lambda x: (x.get("severity", ""), x.get("finding_id", "")))
        ],
        "sourceRefs": sorted(all_refs),
    }


def integrate_manual_review_with_findings(
    integrity_findings: list[IntegrityFinding],
    human_records: list[dict[str, Any]],
    *,
    fixture_id: str = "manual-review-integration",
    profile: str = "default",
    now: str | None = None,
) -> dict[str, Any]:
    """Integrate manual review with existing integrity findings.

    Takes findings from skip_focus, mock_assertion, and coupling detectors,
    processes them for manual review, and generates combined report.
    """
    current_time = now or datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    # Convert IntegrityFinding to dict
    finding_dicts: list[dict[str, Any]] = []
    for f in integrity_findings:
        finding_dicts.append({
            "finding_id": f.finding_id,
            "detector_id": f.detector_id,
            "severity": f.severity,
            "profile": f.profile,
            "affected_test_id": f.affected_test_id,
            "marker_kind": f.marker_kind.value if hasattr(f.marker_kind, "value") else str(f.marker_kind),
            "reason": f.reason,
            "owner": f.owner,
            "expiry": f.expiry,
            "sourceRefs": f.sourceRef if isinstance(f.sourceRef, list) else [f.sourceRef] if f.sourceRef else [],
            "readiness_effect": f.readiness_effect,
            "suggested_manual_review_action": f.suggested_manual_review_action,
            "evidence_class": f.marker_kind.value if hasattr(f.marker_kind, "value") else str(f.marker_kind),
            "manual_review_required": bool(f.suggested_manual_review_action),
            "required_human_decision": f.suggested_manual_review_action,
        })

    return process_manual_review_requests(
        finding_dicts,
        human_records,
        fixture_id=fixture_id,
        profile=profile,
        now=current_time,
    )


def check_human_record_expiry(
    human_records: list[dict[str, Any]],
    *,
    fixture_id: str = "human-record-expiry",
    now: str | None = None,
) -> dict[str, Any]:
    """Check human records for expiry and generate renewal requests.

    Returns report of expired and expiring records.
    """
    current_time = now or datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    expired: list[dict[str, Any]] = []
    expiring_soon: list[dict[str, Any]] = []
    valid: list[dict[str, Any]] = []

    for record in human_records:
        expiry = record.get("expiry", record.get("expiry_date", ""))
        if not expiry:
            # No expiry = always valid
            valid.append({**record, "status": "valid_no_expiry"})
            continue

        if current_time > expiry:
            expired.append({**record, "status": "expired"})
        else:
            # Check if expiring within 30 days
            from datetime import timedelta
            try:
                expiry_dt = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
                current_dt = datetime.fromisoformat(current_time.replace("Z", "+00:00"))
                if (expiry_dt - current_dt).days <= 30:
                    expiring_soon.append({**record, "status": "expiring_soon"})
                else:
                    valid.append({**record, "status": "valid"})
            except (ValueError, TypeError):
                valid.append({**record, "status": "valid_invalid_date"})

    # Generate renewal requests for expired/expiring
    renewal_requests: list[dict[str, Any]] = []
    for record in expired + expiring_soon:
        request_id = f"{fixture_id}.renewal.{record.get('record_id', '')}"
        renewal_requests.append({
            "request_id": request_id,
            "risk_id": record.get("evidence_ref"),
            "owner": record.get("owner"),
            "expiry_date": None,  # To be set on renewal
            "expiry": None,
            "created_at": current_time,
            "source_refs": record.get("source_refs", []),
            "status": "pending_renewal",
            "justification": f"Human record {record.get('status', 'expired')}. Renewal required.",
            "evidence_context": ["human_record_expiry", record.get("record_id", "")],
            "reason": record.get("decision", "Record requires renewal"),
            "blocking": record.get("blocking", False),
            "required_decision": "extend_expiry_or_close",
            "classification": "expired_human_record",
            "sourceRef": record.get("source_refs", [""])[0] if record.get("source_refs") else "",
        })

    # Summary
    summary = {
        "total_records": len(human_records),
        "expired_count": len(expired),
        "expiring_soon_count": len(expiring_soon),
        "valid_count": len(valid),
        "renewal_requests": len(renewal_requests),
    }

    all_refs: set[str] = set()
    for record in human_records:
        for ref in record.get("source_refs", []):
            all_refs.add(ref)

    return {
        "schema_version": "HATE/v1",
        "record_type": "human_record_expiry_report",
        "fixture_id": fixture_id,
        "summary": summary,
        "expired_records": expired,
        "expiring_records": expiring_soon,
        "valid_records": valid,
        "renewal_requests": renewal_requests,
        "sourceRefs": sorted(all_refs),
    }