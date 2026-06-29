from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from .evidence_envelope import source_refs


DEFAULT_EXPIRY_DAYS = 30


def _reason_for_gap(gap_class: str, severity: str) -> str:
    """Generate reason description based on gap class."""
    if gap_class == "missing_execution":
        return f"{severity} risk lacks test execution evidence - manual verification required"
    if gap_class == "no_oracle":
        return f"{severity} risk lacks oracle evidence - manual judgment needed"
    if gap_class == "oracle_weak":
        return f"{severity} risk has weak oracle - manual review to strengthen evidence"
    if gap_class == "missing_oracle":
        return f"{severity} risk requires oracle evidence - manual review required"
    if gap_class == "coverage_gap":
        return f"{severity} risk has coverage gap - manual verification of coverage quality"
    if gap_class == "missing_review":
        return f"{severity} risk requires manual review per policy"
    if gap_class == "blocked_by_static_finding":
        return f"{severity} risk is blocked by static finding - manual disposition required"
    return f"{severity} risk has gap ({gap_class}) - manual review required"


def _required_decision_for_gap(gap_class: str) -> str:
    """Determine required decision based on gap class."""
    if gap_class == "missing_execution":
        return "verify_coverage_or_accept_risk"
    if gap_class == "no_oracle" or gap_class == "missing_oracle":
        return "verify_behavior_or_accept_weakness"
    if gap_class == "oracle_weak":
        return "accept_weak_oracle_or_request_stronger"
    if gap_class == "coverage_gap":
        return "accept_coverage_or_request_test"
    if gap_class == "missing_review":
        return "approve_or_reject"
    if gap_class == "blocked_by_static_finding":
        return "fix_finding_or_accept_suppression"
    return "approve_or_reject"


@dataclass(frozen=True)
class ManualReviewRequest:
    request_id: str
    risk_id: str
    owner: str | None
    expiry_date: str
    expiry: str
    created_at: str
    source_refs: list[str]
    status: str
    justification: str | None
    evidence_context: list[str]
    reason: str  # Why manual review is needed
    blocking: bool  # Whether this blocks release
    required_decision: str  # What decision is expected

    def as_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "risk_id": self.risk_id,
            "owner": self.owner,
            "expiry_date": self.expiry_date,
            "expiry": self.expiry,
            "created_at": self.created_at,
            "source_refs": self.source_refs,
            "status": self.status,
            "justification": self.justification,
            "evidence_context": self.evidence_context,
            "reason": self.reason,
            "blocking": self.blocking,
            "required_decision": self.required_decision,
        }


@dataclass(frozen=True)
class ReviewBridgeFinding:
    code: str
    severity: str
    message: str
    sourceRef: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "sourceRef": self.sourceRef,
        }


def build_manual_review_requests(
    matrix: dict[str, Any],
    *,
    fixture_id: str = "manual-review-bridge",
    now: str | None = None,
    expiry_days: int | None = None,
    owner_override: str | None = None,
) -> dict[str, Any]:
    current_time = now or datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    expiry = expiry_days or DEFAULT_EXPIRY_DAYS

    requests: list[ManualReviewRequest] = []
    findings: list[ReviewBridgeFinding] = []

    # Copy findings from the matrix (including expired debt findings)
    for f in matrix.get("findings", []):
        if f.get("code") in {"accepted_debt_expired", "accepted_debt_invalid_expiry_format"}:
            findings.append(
                ReviewBridgeFinding(
                    code=f.get("code", ""),
                    severity=f.get("severity", "medium"),
                    message=f.get("message", ""),
                    sourceRef=f.get("sourceRefs", [])[0] if f.get("sourceRefs") else "",
                )
            )

    entries_with_manual_gap = [
        entry for entry in matrix.get("entries", [])
        if entry.get("gap_class") in {"oracle_weak", "no_oracle", "missing_execution"}
    ]

    for entry in entries_with_manual_gap:
        risk_id = entry.get("risk_id", "")
        gap_class = entry.get("gap_class", "")
        severity = entry.get("severity", "medium")
        readiness_effect = entry.get("readiness_effect", "hold")

        owner = owner_override
        if owner is None:
            findings.append(
                ReviewBridgeFinding(
                    code="manual_review_missing_owner",
                    severity="hard",
                    message=f"manual review request for risk {risk_id} requires owner assignment",
                    sourceRef=entry.get("sourceRefs", [])[0] if entry.get("sourceRefs") else f"risk:{risk_id}",
                )
            )

        expiry_dt = datetime.fromisoformat(current_time.replace("Z", "+00:00")) + timedelta(days=expiry)
        expiry_date = expiry_dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")

        # Determine reason based on gap_class
        reason = _reason_for_gap(gap_class, severity)

        # Determine blocking based on readiness_effect
        blocking = readiness_effect in {"blocked", "hold"}

        # Determine required_decision based on gap_class
        required_decision = _required_decision_for_gap(gap_class)

        request = ManualReviewRequest(
            request_id=f"manual_review_{risk_id}",
            risk_id=risk_id,
            owner=owner,
            expiry_date=expiry_date,
            expiry=expiry_date,
            created_at=current_time,
            source_refs=entry.get("sourceRefs", []),
            status="pending",
            justification=None,
            evidence_context=entry.get("evidence_nodes", []),
            reason=reason,
            blocking=blocking,
            required_decision=required_decision,
        )
        requests.append(request)

    debt_items = matrix.get("risk_debt", [])
    accepted_debts = [item for item in debt_items if item.get("status") == "accepted"]

    for debt in accepted_debts:
        expiry_str = debt.get("expiry_date")
        if expiry_str:
            try:
                expiry_dt = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
                now_dt = datetime.fromisoformat(current_time.replace("Z", "+00:00"))
                if expiry_dt < now_dt:
                    findings.append(
                        ReviewBridgeFinding(
                            code="accepted_debt_expired",
                            severity="hard",
                            message=f"accepted risk debt {debt.get('risk_debt_id')} has expired",
                            sourceRef=debt.get("source_refs", [])[0] if debt.get("source_refs") else debt.get("risk_debt_id", ""),
                        )
                    )
            except ValueError:
                pass

    overall_status = _compute_bridge_status(requests, findings)

    return {
        "schema_version": "HATE/v1",
        "record_type": "manual_review_request_bundle",
        "fixture_id": fixture_id,
        "summary": {
            "overall_status": overall_status,
            "request_count": len(requests),
            "pending_count": sum(1 for r in requests if r.status == "pending"),
            "hard_dq_count": sum(1 for f in findings if f.severity == "hard"),
            "missing_owner_count": sum(1 for f in findings if f.code == "manual_review_missing_owner"),
            "expired_count": sum(1 for f in findings if f.code == "accepted_debt_expired"),
        },
        "requests": [req.as_dict() for req in requests],
        "findings": [f.as_dict() for f in findings],
        "sourceRefs": sorted({ref for req in requests for ref in req.source_refs}),
    }


def accept_risk_debt(
    debt_item: dict[str, Any],
    *,
    owner: str,
    justification: str,
    expiry_days: int | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    if owner is None or not owner.strip():
        raise ValueError("accept_risk_debt requires non-empty owner")

    if not justification or not justification.strip():
        raise ValueError("accept_risk_debt requires justification")

    current_time = now or datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    expiry = expiry_days or DEFAULT_EXPIRY_DAYS
    expiry_dt = datetime.fromisoformat(current_time.replace("Z", "+00:00")) + timedelta(days=expiry)
    expiry_date = expiry_dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")

    return {
        "risk_debt_id": debt_item.get("risk_debt_id"),
        "debt_type": debt_item.get("debt_type"),
        "severity": debt_item.get("severity"),
        "status": "accepted",
        "risk_id": debt_item.get("risk_id"),
        "owner": owner,
        "created_at": debt_item.get("created_at", current_time),
        "last_seen_at": current_time,
        "age_days": debt_item.get("age_days", 0),
        "source_refs": debt_item.get("source_refs", []),
        "recommended_actions": debt_item.get("recommended_actions", []),
        "blocking_profile": debt_item.get("blocking_profile", []),
        "justification": justification,
        "expiry_date": expiry_date,
    }


def validate_manual_review_request(request: dict[str, Any]) -> list[ReviewBridgeFinding]:
    findings = []

    if not request.get("owner") or not request.get("owner", "").strip():
        findings.append(
            ReviewBridgeFinding(
                code="manual_review_missing_owner",
                severity="hard",
                message=f"manual review request {request.get('request_id', 'unknown')} requires owner",
                sourceRef=request.get("source_refs", [])[0] if request.get("source_refs") else request.get("request_id", "unknown"),
            )
        )

    expiry_str = request.get("expiry_date") or request.get("expiry")
    if expiry_str:
        try:
            expiry_dt = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
            now_dt = datetime.now(UTC)
            if expiry_dt < now_dt:
                findings.append(
                    ReviewBridgeFinding(
                        code="manual_review_expired",
                        severity="hard",
                        message=f"manual review request {request.get('request_id', 'unknown')} has expired",
                        sourceRef=request.get("source_refs", [])[0] if request.get("source_refs") else request.get("request_id", "unknown"),
                    )
                )
        except ValueError:
            findings.append(
                ReviewBridgeFinding(
                    code="invalid_expiry_format",
                    severity="medium",
                    message=f"manual review request {request.get('request_id', 'unknown')} has invalid expiry format",
                    sourceRef=request.get("request_id", "unknown"),
                )
            )

    if not request.get("source_refs") or len(request.get("source_refs", [])) == 0:
        findings.append(
            ReviewBridgeFinding(
                code="manual_review_missing_source_refs",
                severity="medium",
                message=f"manual review request {request.get('request_id', 'unknown')} missing sourceRefs",
                sourceRef=request.get("request_id", "unknown"),
            )
        )

    return findings


def _compute_bridge_status(requests: list[ManualReviewRequest], findings: list[ReviewBridgeFinding]) -> str:
    if any(f.severity == "hard" for f in findings):
        return "blocked"

    pending_count = sum(1 for r in requests if r.status == "pending")
    if pending_count > 0:
        return "pending"

    return "ready"
