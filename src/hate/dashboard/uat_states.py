"""HATE Dashboard UAT State Modeling.

UAT states are read-model projections representing dashboard-facing states.
Each state preserves sourceRefs and upstream report ids, never inventing verdicts.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class UATState:
    """Base class for all UAT states.

    Each state:
    - Preserves sourceRefs linking to upstream report evidence
    - Never computes or invents readiness verdicts
    - Has required UI behavior per UI_WORKFLOW_REQUIREMENTS.md
    """

    state_type: str
    run_id: str
    profile: str
    sourceRefs: list[str]
    upstream_report_ids: list[str] = field(default_factory=list)
    ui_requirements: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat().replace("+00:00", "Z"))

    def to_dict(self) -> dict[str, Any]:
        """Convert to UAT state dict."""
        return {
            "schema_version": "HATE/v1",
            "record_type": "uat-state",
            "state_type": self.state_type,
            "run_id": self.run_id,
            "profile": self.profile,
            "sourceRefs": self.sourceRefs,
            "upstream_report_ids": self.upstream_report_ids,
            "ui_requirements": self.ui_requirements,
            "timestamp": self.timestamp,
        }


@dataclass(kw_only=True)
class ReadyState(UATState):
    """Ready UAT state - run eligible for product release.

    UI Requirements:
    - Show run provenance
    - Show profile
    - Show green/eligible status with sourceRefs
    - No blockers, no manual reviews pending
    """

    state_type: str = "ready"
    overall_status: str = "go"
    blockers: list[dict[str, Any]] = field(default_factory=list)
    manual_review_count: int = 0
    quarantined_artifact_count: int = 0
    missing_report_count: int = 0

    def __post_init__(self) -> None:
        self.ui_requirements = [
            "show_run_provenance",
            "show_profile",
            "show_eligible_status_with_sourceRefs",
            "no_blockers_visible",
            "no_manual_review_pending",
        ]

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["overall_status"] = self.overall_status
        d["blockers"] = self.blockers
        d["manual_review_count"] = self.manual_review_count
        d["quarantined_artifact_count"] = self.quarantined_artifact_count
        d["missing_report_count"] = self.missing_report_count
        return d


@dataclass(kw_only=True)
class SoftGapState(UATState):
    """Soft gap UAT state - conditional but not blocking.

    UI Requirements:
    - Show soft gap count and reasons
    - Link to sourceRefs for each gap
    - Show next actions (optional remediation)
    """

    state_type: str = "soft_gap"
    soft_gap_count: int = 0
    soft_gaps: list[dict[str, Any]] = field(default_factory=list)
    overall_status: str = "conditional"

    def __post_init__(self) -> None:
        self.ui_requirements = [
            "show_soft_gap_count",
            "show_gap_reasons_with_sourceRefs",
            "show_conditional_status",
            "show_next_actions_optional",
        ]

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["soft_gap_count"] = self.soft_gap_count
        d["soft_gaps"] = self.soft_gaps
        d["overall_status"] = self.overall_status
        return d


@dataclass(kw_only=True)
class HoldRiskState(UATState):
    """Hold due to risk without oracle evidence.

    UI Requirements:
    - Show oracle missing count
    - Link to risk coverage matrix sourceRefs
    - Show risk severity and description
    - Cannot show product-ready
    """

    state_type: str = "hold_risk"
    oracle_missing_count: int = 0
    unsupported_claim_count: int = 0
    unsupported_claims: list[dict[str, Any]] = field(default_factory=list)
    overall_status: str = "hold"

    def __post_init__(self) -> None:
        self.ui_requirements = [
            "show_oracle_missing_count",
            "link_to_risk_coverage_sourceRefs",
            "show_risk_severity_description",
            "cannot_show_product_ready",
        ]

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["oracle_missing_count"] = self.oracle_missing_count
        d["unsupported_claim_count"] = self.unsupported_claim_count
        d["unsupported_claims"] = self.unsupported_claims
        d["overall_status"] = self.overall_status
        return d


@dataclass(kw_only=True)
class HardDQSecurityState(UATState):
    """Hard DQ due to security/adapters/parse failure.

    UI Requirements:
    - Show hard DQ reason and severity
    - Link to adapter/safety report sourceRefs
    - Cannot proceed without resolution
    - Show remediation actions
    """

    state_type: str = "hard_dq_security"
    hard_dq_count: int = 1
    hard_dqs: list[dict[str, Any]] = field(default_factory=list)
    overall_status: str = "block"
    severity: str = "critical"

    def __post_init__(self) -> None:
        self.ui_requirements = [
            "show_hard_dq_reason",
            "show_severity_not_color_only",
            "link_to_sourceRefs",
            "cannot_proceed_without_resolution",
            "show_remediation_actions",
        ]

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["hard_dq_count"] = self.hard_dq_count
        d["hard_dqs"] = self.hard_dqs
        d["overall_status"] = self.overall_status
        d["severity"] = self.severity
        return d


@dataclass(kw_only=True)
class ManualReviewPendingState(UATState):
    """Manual review required and pending.

    UI Requirements:
    - Show review request with owner visible
    - Show expiry and overdue status
    - Link to risk_ref sourceRefs
    - Cannot claim complete until human record exists
    """

    state_type: str = "manual_review_pending"
    pending_reviews: list[dict[str, Any]] = field(default_factory=list)
    total_count: int = 0
    overdue_count: int = 0
    overall_status: str = "hold"

    def __post_init__(self) -> None:
        self.ui_requirements = [
            "show_owner_visible",
            "show_expiry_overdue_status",
            "link_to_risk_ref_sourceRefs",
            "cannot_claim_complete_until_human_record",
        ]

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["pending_reviews"] = self.pending_reviews
        d["total_count"] = self.total_count
        d["overdue_count"] = self.overdue_count
        d["overall_status"] = self.overall_status
        return d


@dataclass(kw_only=True)
class QuarantinedArtifactState(UATState):
    """Artifact quarantined for safety.

    UI Requirements:
    - Show safe metadata only (hashed artifact_id)
    - Show quarantine reason
    - No raw artifact link
    - Show remediation contact
    """

    state_type: str = "quarantined_artifact"
    artifact_id: str = ""
    classification: str = "restricted"
    quarantine_reason: str = ""
    safe_metadata_only: bool = True
    remediation: str = "Contact security team for quarantine review"

    def __post_init__(self) -> None:
        self.ui_requirements = [
            "show_safe_metadata_only",
            "show_quarantine_reason",
            "no_raw_artifact_link",
            "show_remediation_contact",
        ]

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        # Safe metadata only: hashed artifact_id, no raw content
        if self.safe_metadata_only:
            safe_id = hashlib.sha256(self.artifact_id.encode()).hexdigest()[:16]
            d["artifact_id_safe"] = safe_id
            d["safe_metadata_only"] = True
            d["remediation"] = self.remediation
        else:
            d["artifact_id"] = self.artifact_id
            d["safe_metadata_only"] = False
        d["classification"] = self.classification
        d["quarantine_reason"] = self.quarantine_reason
        return d


@dataclass(kw_only=True)
class MissingOracleState(UATState):
    """Missing oracle for covered risk.

    UI Requirements:
    - Show oracle missing count
    - Link to risk coverage matrix
    - Show affected risks
    - Cannot claim oracle-verified
    """

    state_type: str = "missing_oracle"
    oracle_missing_count: int = 0
    affected_risks: list[dict[str, Any]] = field(default_factory=list)
    overall_status: str = "hold"

    def __post_init__(self) -> None:
        self.ui_requirements = [
            "show_oracle_missing_count",
            "link_to_risk_coverage_sourceRefs",
            "show_affected_risks",
            "cannot_claim_oracle_verified",
        ]

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["oracle_missing_count"] = self.oracle_missing_count
        d["affected_risks"] = self.affected_risks
        d["overall_status"] = self.overall_status
        return d


@dataclass(kw_only=True)
class CoverageOnlyState(UATState):
    """Coverage-only evidence (no execution result).

    UI Requirements:
    - Show coverage_only count
    - Link to risk coverage matrix
    - Show that evidence is coverage-only, not execution
    - Cannot claim execution-complete
    """

    state_type: str = "coverage_only"
    coverage_only_count: int = 0
    coverage_only_risks: list[dict[str, Any]] = field(default_factory=list)
    overall_status: str = "conditional"

    def __post_init__(self) -> None:
        self.ui_requirements = [
            "show_coverage_only_count",
            "link_to_risk_coverage_sourceRefs",
            "show_evidence_is_coverage_only",
            "cannot_claim_execution_complete",
        ]

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["coverage_only_count"] = self.coverage_only_count
        d["coverage_only_risks"] = self.coverage_only_risks
        d["overall_status"] = self.overall_status
        return d


@dataclass(kw_only=True)
class UnsupportedClaimState(UATState):
    """Unsupported claim in product readiness report.

    UI Requirements:
    - Show unsupported claim count
    - Link to claim sourceRefs
    - Show reason for unsupported
    - Cannot claim product-ready
    """

    state_type: str = "unsupported_claim"
    unsupported_claim_count: int = 0
    unsupported_claims: list[dict[str, Any]] = field(default_factory=list)
    overall_status: str = "hold"

    def __post_init__(self) -> None:
        self.ui_requirements = [
            "show_unsupported_claim_count",
            "link_to_claim_sourceRefs",
            "show_reason_for_unsupported",
            "cannot_claim_product_ready",
        ]

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["unsupported_claim_count"] = self.unsupported_claim_count
        d["unsupported_claims"] = self.unsupported_claims
        d["overall_status"] = self.overall_status
        return d


# Builder functions - project from reports without computing verdicts


def build_ready_state(
    readiness_report: dict[str, Any],
    run_id: str,
    profile: str,
) -> ReadyState:
    """Build ReadyState from readiness report (projection only)."""
    summary = readiness_report.get("summary", {})
    return ReadyState(
        run_id=run_id,
        profile=profile,
        sourceRefs=readiness_report.get("sourceRefs", []),
        upstream_report_ids=[readiness_report.get("schema_version", "HATE/v1")],
        overall_status=summary.get("overall_status", "go"),
        blockers=readiness_report.get("hard_dqs", []),
        manual_review_count=0,
        quarantined_artifact_count=0,
        missing_report_count=0,
    )


def build_soft_gap_state(
    readiness_report: dict[str, Any],
    run_id: str,
    profile: str,
) -> SoftGapState:
    """Build SoftGapState from readiness report."""
    summary = readiness_report.get("summary", {})
    soft_gaps = readiness_report.get("soft_gaps", [])
    return SoftGapState(
        run_id=run_id,
        profile=profile,
        sourceRefs=readiness_report.get("sourceRefs", []),
        upstream_report_ids=[readiness_report.get("schema_version", "HATE/v1")],
        soft_gap_count=len(soft_gaps),
        soft_gaps=soft_gaps,
        overall_status=summary.get("overall_status", "conditional"),
    )


def build_hold_risk_state(
    readiness_report: dict[str, Any],
    risk_coverage_matrix: dict[str, Any],
    run_id: str,
    profile: str,
) -> HoldRiskState:
    """Build HoldRiskState from readiness report and risk coverage matrix."""
    summary = readiness_report.get("summary", {})
    unsupported_claims = readiness_report.get("unsupported_claims", [])

    # Count oracle missing from risk coverage matrix
    oracle_missing_count = 0
    for risk in risk_coverage_matrix.get("risks", []):
        if risk.get("oracle_evidence") is False:
            oracle_missing_count += 1

    return HoldRiskState(
        run_id=run_id,
        profile=profile,
        sourceRefs=list(
            set(readiness_report.get("sourceRefs", []) + risk_coverage_matrix.get("sourceRefs", []))
        ),
        upstream_report_ids=[
            readiness_report.get("schema_version", "HATE/v1"),
            risk_coverage_matrix.get("schema_version", "HATE/v1"),
        ],
        oracle_missing_count=oracle_missing_count,
        unsupported_claim_count=len(unsupported_claims),
        unsupported_claims=unsupported_claims,
        overall_status=summary.get("overall_status", "hold"),
    )


def build_hard_dq_security_state(
    readiness_report: dict[str, Any],
    artifact_safety_report: dict[str, Any] | None = None,
    run_id: str = "",
    profile: str = "",
) -> HardDQSecurityState:
    """Build HardDQSecurityState from readiness report and safety report."""
    summary = readiness_report.get("summary", {})
    hard_dqs = readiness_report.get("hard_dqs", [])

    source_refs = readiness_report.get("sourceRefs", [])
    if artifact_safety_report:
        source_refs.extend(artifact_safety_report.get("sourceRefs", []))

    severity = "critical"
    if hard_dqs:
        severity = hard_dqs[0].get("severity", "critical")

    return HardDQSecurityState(
        run_id=run_id,
        profile=profile,
        sourceRefs=source_refs,
        upstream_report_ids=[readiness_report.get("schema_version", "HATE/v1")],
        hard_dq_count=len(hard_dqs),
        hard_dqs=hard_dqs,
        overall_status=summary.get("overall_status", "block"),
        severity=severity,
    )


def build_manual_review_pending_state(
    manual_review_requests: list[dict[str, Any]],
    run_id: str,
    profile: str,
) -> ManualReviewPendingState:
    """Build ManualReviewPendingState from review requests."""
    now = datetime.now(UTC)

    pending_reviews = []
    overdue_count = 0

    for request in manual_review_requests:
        review = {
            "review_id": request.get("request_id"),
            "owner": request.get("owner"),
            "status": request.get("status"),
            "risk_ref": request.get("risk_ref"),
            "expires_at": request.get("expires_at"),
            "sourceRef": request.get("sourceRef"),
            "is_overdue": False,
        }

        # Check overdue
        expires_at_str = request.get("expires_at")
        if expires_at_str:
            expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
            if now > expires_at:
                review["is_overdue"] = True
                overdue_count += 1

        pending_reviews.append(review)

    source_refs = [r.get("sourceRef", "") for r in manual_review_requests if r.get("sourceRef")]

    return ManualReviewPendingState(
        run_id=run_id,
        profile=profile,
        sourceRefs=source_refs,
        upstream_report_ids=[],
        pending_reviews=pending_reviews,
        total_count=len(pending_reviews),
        overdue_count=overdue_count,
        overall_status="hold",
    )


def build_quarantined_artifact_state(
    artifact_safety_report: dict[str, Any],
    run_id: str,
    profile: str,
) -> QuarantinedArtifactState:
    """Build QuarantinedArtifactState from safety report."""
    findings = artifact_safety_report.get("findings", [])
    quarantine_reason = ""
    if findings:
        quarantine_reason = findings[0].get("reason", "Security risk detected")

    return QuarantinedArtifactState(
        run_id=run_id,
        profile=profile,
        sourceRefs=artifact_safety_report.get("sourceRefs", []),
        upstream_report_ids=[artifact_safety_report.get("schema_version", "HATE/v1")],
        artifact_id=artifact_safety_report.get("artifact_id", ""),
        classification=artifact_safety_report.get("classification", "restricted"),
        quarantine_reason=quarantine_reason,
        safe_metadata_only=True,
        remediation="Contact security team for quarantine review",
    )


def build_missing_oracle_state(
    risk_coverage_matrix: dict[str, Any],
    run_id: str,
    profile: str,
) -> MissingOracleState:
    """Build MissingOracleState from risk coverage matrix."""
    affected_risks = []
    oracle_missing_count = 0

    for risk in risk_coverage_matrix.get("risks", []):
        if risk.get("oracle_evidence") is False:
            oracle_missing_count += 1
            affected_risks.append({
                "risk_id": risk.get("risk_id"),
                "severity": risk.get("severity"),
                "description": risk.get("description"),
                "sourceRef": risk.get("sourceRef"),
            })

    return MissingOracleState(
        run_id=run_id,
        profile=profile,
        sourceRefs=risk_coverage_matrix.get("sourceRefs", []),
        upstream_report_ids=[risk_coverage_matrix.get("schema_version", "HATE/v1")],
        oracle_missing_count=oracle_missing_count,
        affected_risks=affected_risks,
        overall_status="hold",
    )


def build_coverage_only_state(
    risk_coverage_matrix: dict[str, Any],
    run_id: str,
    profile: str,
) -> CoverageOnlyState:
    """Build CoverageOnlyState from risk coverage matrix."""
    coverage_only_risks = []
    coverage_only_count = 0

    for risk in risk_coverage_matrix.get("risks", []):
        if risk.get("coverage_status") == "coverage_only":
            coverage_only_count += 1
            coverage_only_risks.append({
                "risk_id": risk.get("risk_id"),
                "severity": risk.get("severity"),
                "description": risk.get("description"),
                "sourceRef": risk.get("sourceRef"),
            })

    return CoverageOnlyState(
        run_id=run_id,
        profile=profile,
        sourceRefs=risk_coverage_matrix.get("sourceRefs", []),
        upstream_report_ids=[risk_coverage_matrix.get("schema_version", "HATE/v1")],
        coverage_only_count=coverage_only_count,
        coverage_only_risks=coverage_only_risks,
        overall_status="conditional",
    )


def build_unsupported_claim_state(
    readiness_report: dict[str, Any],
    run_id: str,
    profile: str,
) -> UnsupportedClaimState:
    """Build UnsupportedClaimState from readiness report."""
    unsupported_claims = readiness_report.get("unsupported_claims", [])
    summary = readiness_report.get("summary", {})

    return UnsupportedClaimState(
        run_id=run_id,
        profile=profile,
        sourceRefs=readiness_report.get("sourceRefs", []),
        upstream_report_ids=[readiness_report.get("schema_version", "HATE/v1")],
        unsupported_claim_count=len(unsupported_claims),
        unsupported_claims=unsupported_claims,
        overall_status=summary.get("overall_status", "hold"),
    )
