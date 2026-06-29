"""HATE Dashboard View Models.

Dashboard-ready projections from HATE reports. The UI is a read-model consumer.
It must not compute, override, or hide HATE verdicts.

Key constraints:
- No independent verdict computation
- Unsafe artifacts shown with safe metadata only
- Missing reports shown as blockers
- sourceRefs link to report evidence
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any


class RunOverviewViewModel:
    """Run overview view model for dashboard.

    Shows run provenance, readiness, DQ counts, artifact safety, and blockers.
    Does not compute verdicts - projects from product-readiness-report.
    """

    def __init__(
        self,
        run_id: str,
        profile: str,
        overall_status: str,
        hard_dq_count: int,
        soft_gap_count: int,
        unsupported_claim_count: int,
        manual_review_count: int,
        quarantined_artifact_count: int,
        missing_report_count: int,
        sourceRefs: list[str],
        blockers: list[dict[str, Any]],
        next_actions: list[dict[str, str]],
        stale_status: str | None = None,
        view_id: str | None = None,
    ) -> None:
        self.run_id = run_id
        self.profile = profile
        self.overall_status = overall_status
        self.hard_dq_count = hard_dq_count
        self.soft_gap_count = soft_gap_count
        self.unsupported_claim_count = unsupported_claim_count
        self.manual_review_count = manual_review_count
        self.quarantined_artifact_count = quarantined_artifact_count
        self.missing_report_count = missing_report_count
        self.sourceRefs = sourceRefs
        self.blockers = blockers
        self.next_actions = next_actions
        self.stale_status = stale_status
        self.view_id = view_id or f"view-run-{uuid.uuid4().hex[:8]}"
        self.created_at = datetime.now(UTC).isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dashboard view dict."""
        return {
            "schema_version": "HATE/v1",
            "record_type": "run-overview-view-model",
            "view_id": self.view_id,
            "run_id": self.run_id,
            "profile": self.profile,
            "overall_status": self.overall_status,
            "hard_dq_count": self.hard_dq_count,
            "soft_gap_count": self.soft_gap_count,
            "unsupported_claim_count": self.unsupported_claim_count,
            "manual_review_count": self.manual_review_count,
            "quarantined_artifact_count": self.quarantined_artifact_count,
            "missing_report_count": self.missing_report_count,
            "blockers": self.blockers,
            "next_actions": self.next_actions,
            "sourceRefs": self.sourceRefs,
            "stale_status": self.stale_status,
            "created_at": self.created_at,
        }

    def is_ready(self) -> bool:
        """Check if run is product-ready (no blockers)."""
        return (
            self.overall_status == "go"
            and self.hard_dq_count == 0
            and self.missing_report_count == 0
            and self.quarantined_artifact_count == 0
        )


class ArtifactSafetyViewModel:
    """Artifact safety view model for dashboard.

    Shows artifact safety status with safe metadata only for quarantined artifacts.
    Never exposes raw quarantined content or restricted paths.
    """

    def __init__(
        self,
        artifact_id: str,
        classification: str,
        quarantine_status: str,
        redaction_status: str,
        safe_metadata_only: bool,
        quarantine_reason: str | None,
        sourceRefs: list[str],
        view_id: str | None = None,
    ) -> None:
        self.artifact_id = artifact_id
        self.classification = classification
        self.quarantine_status = quarantine_status
        self.redaction_status = redaction_status
        self.safe_metadata_only = safe_metadata_only
        self.quarantine_reason = quarantine_reason
        self.sourceRefs = sourceRefs
        self.view_id = view_id or f"view-artifact-{uuid.uuid4().hex[:8]}"
        self.created_at = datetime.now(UTC).isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dashboard view dict (safe metadata only for quarantined)."""
        if self.safe_metadata_only:
            # Safe metadata: no raw content, no paths, hashed artifact_id
            safe_id = hashlib.sha256(self.artifact_id.encode()).hexdigest()[:16]
            return {
                "schema_version": "HATE/v1",
                "record_type": "artifact-safety-view-model",
                "view_id": self.view_id,
                "artifact_id_safe": safe_id,
                "classification": self.classification,
                "quarantine_status": self.quarantine_status,
                "redaction_status": self.redaction_status,
                "safe_metadata_only": True,
                "quarantine_reason": self.quarantine_reason,
                "sourceRefs": self.sourceRefs,
                "remediation": "Contact security team for quarantine review",
                "created_at": self.created_at,
            }
        else:
            return {
                "schema_version": "HATE/v1",
                "record_type": "artifact-safety-view-model",
                "view_id": self.view_id,
                "artifact_id": self.artifact_id,
                "classification": self.classification,
                "quarantine_status": self.quarantine_status,
                "redaction_status": self.redaction_status,
                "safe_metadata_only": False,
                "sourceRefs": self.sourceRefs,
                "created_at": self.created_at,
            }


class ManualReviewQueueViewModel:
    """Manual review queue view model for dashboard.

    Shows pending manual reviews with owner, expiry, and next actions.
    """

    def __init__(
        self,
        pending_reviews: list[dict[str, Any]],
        total_count: int,
        overdue_count: int,
        sourceRefs: list[str],
        view_id: str | None = None,
    ) -> None:
        self.pending_reviews = pending_reviews
        self.total_count = total_count
        self.overdue_count = overdue_count
        self.sourceRefs = sourceRefs
        self.view_id = view_id or f"view-review-{uuid.uuid4().hex[:8]}"
        self.created_at = datetime.now(UTC).isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dashboard view dict."""
        return {
            "schema_version": "HATE/v1",
            "record_type": "manual-review-queue-view-model",
            "view_id": self.view_id,
            "pending_reviews": self.pending_reviews,
            "total_count": self.total_count,
            "overdue_count": self.overdue_count,
            "sourceRefs": self.sourceRefs,
            "created_at": self.created_at,
        }


class RiskCoverageViewModel:
    """Risk coverage view model for dashboard.

    Shows risks with evidence status, oracle coverage, and gaps.
    """

    def __init__(
        self,
        risk_count: int,
        covered_count: int,
        uncovered_count: int,
        oracle_missing_count: int,
        coverage_only_count: int,
        high_severity_uncovered: list[dict[str, Any]],
        sourceRefs: list[str],
        view_id: str | None = None,
    ) -> None:
        self.risk_count = risk_count
        self.covered_count = covered_count
        self.uncovered_count = uncovered_count
        self.oracle_missing_count = oracle_missing_count
        self.coverage_only_count = coverage_only_count
        self.high_severity_uncovered = high_severity_uncovered
        self.sourceRefs = sourceRefs
        self.view_id = view_id or f"view-risk-{uuid.uuid4().hex[:8]}"
        self.created_at = datetime.now(UTC).isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dashboard view dict."""
        return {
            "schema_version": "HATE/v1",
            "record_type": "risk-coverage-view-model",
            "view_id": self.view_id,
            "risk_count": self.risk_count,
            "covered_count": self.covered_count,
            "uncovered_count": self.uncovered_count,
            "oracle_missing_count": self.oracle_missing_count,
            "coverage_only_count": self.coverage_only_count,
            "high_severity_uncovered": self.high_severity_uncovered,
            "sourceRefs": self.sourceRefs,
            "created_at": self.created_at,
        }


class DashboardViewModel:
    """Combined dashboard view model.

    Aggregates all view models for a single dashboard view.
    """

    def __init__(
        self,
        run_overview: RunOverviewViewModel,
        artifact_safety: list[ArtifactSafetyViewModel],
        manual_review_queue: ManualReviewQueueViewModel | None,
        risk_coverage: RiskCoverageViewModel | None,
        view_id: str | None = None,
    ) -> None:
        self.run_overview = run_overview
        self.artifact_safety = artifact_safety
        self.manual_review_queue = manual_review_queue
        self.risk_coverage = risk_coverage
        self.view_id = view_id or f"view-dashboard-{uuid.uuid4().hex[:8]}"
        self.created_at = datetime.now(UTC).isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dashboard view dict."""
        return {
            "schema_version": "HATE/v1",
            "record_type": "dashboard-view-model",
            "view_id": self.view_id,
            "run_overview": self.run_overview.to_dict(),
            "artifact_safety": [a.to_dict() for a in self.artifact_safety],
            "manual_review_queue": (
                self.manual_review_queue.to_dict() if self.manual_review_queue else None
            ),
            "risk_coverage": (
                self.risk_coverage.to_dict() if self.risk_coverage else None
            ),
            "sourceRefs": self.run_overview.sourceRefs,
            "created_at": self.created_at,
        }


# Builder functions - project from reports, never compute verdicts


def build_run_overview_view_model(
    readiness_report: dict[str, Any],
    run_id: str,
    profile: str,
    artifact_safety_reports: list[dict[str, Any]] | None = None,
    manual_review_requests: list[dict[str, Any]] | None = None,
    missing_reports: list[str] | None = None,
) -> RunOverviewViewModel:
    """Build run overview view model from product readiness report.

    Projects status from report, does not compute verdicts.
    """
    summary = readiness_report.get("summary", {})
    overall_status = summary.get("overall_status", "block")

    hard_dqs = readiness_report.get("hard_dqs", [])
    soft_gaps = readiness_report.get("soft_gaps", [])
    unsupported_claims = readiness_report.get("unsupported_claims", [])

    # Count quarantined artifacts
    quarantined_count = 0
    if artifact_safety_reports:
        quarantined_count = sum(
            1 for r in artifact_safety_reports if r.get("quarantine_required", False)
        )

    # Count manual reviews
    review_count = 0
    if manual_review_requests:
        review_count = len(manual_review_requests)

    # Missing reports count
    missing_count = len(missing_reports or [])

    # Build blockers from report findings
    blockers = []
    for dq in hard_dqs[:5]:  # Limit to top 5
        blockers.append({
            "type": "hard_dq",
            "reason": dq.get("reason", "Unknown hard DQ"),
            "sourceRef": dq.get("sourceRef", ""),
        })
    for missing in missing_reports or []:
        blockers.append({
            "type": "missing_report",
            "reason": f"Missing required report: {missing}",
            "sourceRef": "dashboard/view_models.py:missing_report_check",
        })

    # Build next actions
    next_actions = []
    if overall_status != "go":
        if hard_dqs:
            next_actions.append({
                "action": "resolve_hard_dq",
                "label": "Review hard DQ findings",
                "link": "run-overview#hard-dq",
            })
        if missing_reports:
            next_actions.append({
                "action": "generate_missing_report",
                "label": "Generate missing reports",
                "link": "run-overview#missing-reports",
            })
        if quarantined_count > 0:
            next_actions.append({
                "action": "review_quarantine",
                "label": "Review quarantined artifacts",
                "link": "artifact-safety#quarantine",
            })

    sourceRefs = readiness_report.get("sourceRefs", [])

    return RunOverviewViewModel(
        run_id=run_id,
        profile=profile,
        overall_status=overall_status,
        hard_dq_count=len(hard_dqs),
        soft_gap_count=len(soft_gaps),
        unsupported_claim_count=len(unsupported_claims),
        manual_review_count=review_count,
        quarantined_artifact_count=quarantined_count,
        missing_report_count=missing_count,
        sourceRefs=sourceRefs,
        blockers=blockers,
        next_actions=next_actions,
    )


def build_artifact_safety_view_model(
    artifact_safety_report: dict[str, Any],
) -> ArtifactSafetyViewModel:
    """Build artifact safety view model from artifact safety report.

    Shows safe metadata only for quarantined artifacts.
    """
    quarantine_required = artifact_safety_report.get("quarantine_required", False)
    redaction_required = artifact_safety_report.get("redaction_required", False)

    quarantine_status = "quarantined" if quarantine_required else "none"
    redaction_status = "required" if redaction_required else "not_required"

    # Safe metadata only for quarantined or restricted
    safe_metadata_only = quarantine_required or artifact_safety_report.get(
        "classification", "public"
    ) in ["confidential", "restricted"]

    # Get quarantine reason from first finding
    quarantine_reason = None
    if quarantine_required:
        findings = artifact_safety_report.get("findings", [])
        if findings:
            quarantine_reason = findings[0].get("reason", "Quarantined for safety")

    sourceRefs = artifact_safety_report.get("sourceRefs", [])

    return ArtifactSafetyViewModel(
        artifact_id=artifact_safety_report.get("artifact_id", ""),
        classification=artifact_safety_report.get("classification", "public"),
        quarantine_status=quarantine_status,
        redaction_status=redaction_status,
        safe_metadata_only=safe_metadata_only,
        quarantine_reason=quarantine_reason,
        sourceRefs=sourceRefs,
    )


def build_manual_review_queue_view_model(
    manual_review_requests: list[dict[str, Any]],
) -> ManualReviewQueueViewModel:
    """Build manual review queue view model.

    Shows pending reviews with owner, expiry, and overdue status.
    """
    pending_reviews = []
    overdue_count = 0

    now = datetime.now(UTC)

    for request in manual_review_requests:
        review_id = request.get("request_id", "")
        owner = request.get("owner", "")
        status = request.get("status", "pending")

        # Check overdue
        expires_at = request.get("expires_at")
        is_overdue = False
        if expires_at and status == "pending":
            try:
                expiry_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                is_overdue = now > expiry_dt
                if is_overdue:
                    overdue_count += 1
            except (ValueError, TypeError):
                pass

        pending_reviews.append({
            "review_id": review_id,
            "owner": owner,
            "status": status,
            "risk_ref": request.get("risk_ref", ""),
            "evidence_type": request.get("evidence_type", ""),
            "is_overdue": is_overdue,
            "expires_at": expires_at,
            "sourceRef": request.get("sourceRef", ""),
        })

    sourceRefs = [r.get("sourceRef", "") for r in manual_review_requests if r.get("sourceRef")]

    return ManualReviewQueueViewModel(
        pending_reviews=pending_reviews,
        total_count=len(pending_reviews),
        overdue_count=overdue_count,
        sourceRefs=sourceRefs,
    )


def build_risk_coverage_view_model(
    risk_coverage_matrix: dict[str, Any],
) -> RiskCoverageViewModel:
    """Build risk coverage view model.

    Shows risks with coverage status, oracle coverage, and gaps.
    """
    risks = risk_coverage_matrix.get("risks", [])

    covered_count = 0
    uncovered_count = 0
    oracle_missing_count = 0
    coverage_only_count = 0
    high_severity_uncovered = []

    for risk in risks:
        coverage_status = risk.get("coverage_status", "uncovered")
        has_oracle = risk.get("oracle_evidence", False)
        severity = risk.get("severity", "medium")

        if coverage_status == "covered":
            covered_count += 1
            if not has_oracle:
                oracle_missing_count += 1
        elif coverage_status == "coverage_only":
            coverage_only_count += 1
        else:
            uncovered_count += 1
            if severity in ["high", "critical"]:
                high_severity_uncovered.append({
                    "risk_id": risk.get("risk_id", ""),
                    "severity": severity,
                    "description": risk.get("description", ""),
                    "sourceRef": risk.get("sourceRef", ""),
                })

    sourceRefs = risk_coverage_matrix.get("sourceRefs", [])

    return RiskCoverageViewModel(
        risk_count=len(risks),
        covered_count=covered_count,
        uncovered_count=uncovered_count,
        oracle_missing_count=oracle_missing_count,
        coverage_only_count=coverage_only_count,
        high_severity_uncovered=high_severity_uncovered,
        sourceRefs=sourceRefs,
    )


def build_dashboard_view_model(
    readiness_report: dict[str, Any],
    run_id: str,
    profile: str,
    artifact_safety_reports: list[dict[str, Any]] | None = None,
    manual_review_requests: list[dict[str, Any]] | None = None,
    risk_coverage_matrix: dict[str, Any] | None = None,
    missing_reports: list[str] | None = None,
) -> DashboardViewModel:
    """Build combined dashboard view model.

    Aggregates all view models from reports.
    Does not compute verdicts - projects from product-readiness-report.
    """
    run_overview = build_run_overview_view_model(
        readiness_report=readiness_report,
        run_id=run_id,
        profile=profile,
        artifact_safety_reports=artifact_safety_reports,
        manual_review_requests=manual_review_requests,
        missing_reports=missing_reports,
    )

    artifact_safety = []
    if artifact_safety_reports:
        artifact_safety = [
            build_artifact_safety_view_model(r) for r in artifact_safety_reports
        ]

    manual_review_queue = None
    if manual_review_requests:
        manual_review_queue = build_manual_review_queue_view_model(manual_review_requests)

    risk_coverage = None
    if risk_coverage_matrix:
        risk_coverage = build_risk_coverage_view_model(risk_coverage_matrix)

    return DashboardViewModel(
        run_overview=run_overview,
        artifact_safety=artifact_safety,
        manual_review_queue=manual_review_queue,
        risk_coverage=risk_coverage,
    )