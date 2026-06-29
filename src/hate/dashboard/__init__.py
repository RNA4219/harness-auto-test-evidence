"""HATE Dashboard view models and UAT states module."""

from __future__ import annotations

from hate.dashboard.view_models import (
    DashboardViewModel,
    RunOverviewViewModel,
    ArtifactSafetyViewModel,
    ManualReviewQueueViewModel,
    RiskCoverageViewModel,
    build_run_overview_view_model,
    build_artifact_safety_view_model,
    build_manual_review_queue_view_model,
    build_risk_coverage_view_model,
    build_dashboard_view_model,
)

from hate.dashboard.uat_states import (
    UATState,
    ReadyState,
    SoftGapState,
    HoldRiskState,
    HardDQSecurityState,
    ManualReviewPendingState,
    QuarantinedArtifactState,
    MissingOracleState,
    CoverageOnlyState,
    UnsupportedClaimState,
    build_ready_state,
    build_soft_gap_state,
    build_hold_risk_state,
    build_hard_dq_security_state,
    build_manual_review_pending_state,
    build_quarantined_artifact_state,
    build_missing_oracle_state,
    build_coverage_only_state,
    build_unsupported_claim_state,
)

__all__ = [
    # View models
    "DashboardViewModel",
    "RunOverviewViewModel",
    "ArtifactSafetyViewModel",
    "ManualReviewQueueViewModel",
    "RiskCoverageViewModel",
    "build_run_overview_view_model",
    "build_artifact_safety_view_model",
    "build_manual_review_queue_view_model",
    "build_risk_coverage_view_model",
    "build_dashboard_view_model",
    # UAT states
    "UATState",
    "ReadyState",
    "SoftGapState",
    "HoldRiskState",
    "HardDQSecurityState",
    "ManualReviewPendingState",
    "QuarantinedArtifactState",
    "MissingOracleState",
    "CoverageOnlyState",
    "UnsupportedClaimState",
    "build_ready_state",
    "build_soft_gap_state",
    "build_hold_risk_state",
    "build_hard_dq_security_state",
    "build_manual_review_pending_state",
    "build_quarantined_artifact_state",
    "build_missing_oracle_state",
    "build_coverage_only_state",
    "build_unsupported_claim_state",
]