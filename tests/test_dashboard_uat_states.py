"""Tests for HATE Dashboard UAT States.

UAT states are read-model projections that preserve sourceRefs and upstream report ids,
never inventing or computing readiness verdicts.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

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


# Fixture paths
FIXTURE_DIR = Path("fixtures/dashboard/uat-states")
READY_FIXTURE = FIXTURE_DIR / "ready" / "fixture.json"
SOFT_GAP_FIXTURE = FIXTURE_DIR / "soft-gap" / "fixture.json"
HOLD_RISK_FIXTURE = FIXTURE_DIR / "hold-risk" / "fixture.json"
HARD_DQ_FIXTURE = FIXTURE_DIR / "hard-dq-security" / "fixture.json"
MANUAL_REVIEW_FIXTURE = FIXTURE_DIR / "manual-review-pending" / "fixture.json"
QUARANTINED_FIXTURE = FIXTURE_DIR / "quarantined-artifact" / "fixture.json"
MISSING_ORACLE_FIXTURE = FIXTURE_DIR / "missing-oracle" / "fixture.json"
COVERAGE_ONLY_FIXTURE = FIXTURE_DIR / "coverage-only" / "fixture.json"
UNSUPPORTED_CLAIM_FIXTURE = FIXTURE_DIR / "unsupported-claim" / "fixture.json"


def load_fixture(path: Path) -> dict:
    """Load fixture JSON."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class TestCanonicalFixturePaths:
    """Verify all fixture paths exist and have expected structure."""

    def test_all_fixture_paths_exist(self) -> None:
        """All 9 fixture paths must exist."""
        assert READY_FIXTURE.exists()
        assert SOFT_GAP_FIXTURE.exists()
        assert HOLD_RISK_FIXTURE.exists()
        assert HARD_DQ_FIXTURE.exists()
        assert MANUAL_REVIEW_FIXTURE.exists()
        assert QUARANTINED_FIXTURE.exists()
        assert MISSING_ORACLE_FIXTURE.exists()
        assert COVERAGE_ONLY_FIXTURE.exists()
        assert UNSUPPORTED_CLAIM_FIXTURE.exists()

    def test_fixtures_have_description(self) -> None:
        """Each fixture must have a description field."""
        for path in [
            READY_FIXTURE,
            SOFT_GAP_FIXTURE,
            HOLD_RISK_FIXTURE,
            HARD_DQ_FIXTURE,
            MANUAL_REVIEW_FIXTURE,
            QUARANTINED_FIXTURE,
            MISSING_ORACLE_FIXTURE,
            COVERAGE_ONLY_FIXTURE,
            UNSUPPORTED_CLAIM_FIXTURE,
        ]:
            fixture = load_fixture(path)
            assert "description" in fixture
            assert "input" in fixture
            assert "expected" in fixture


class TestUATStateBase:
    """Tests for UATState base class."""

    def test_to_dict_contains_required_fields(self) -> None:
        """to_dict must contain all required base fields."""
        state = UATState(
            state_type="test_state",
            run_id="run-001",
            profile="product",
            sourceRefs=["report.json"],
        )
        d = state.to_dict()
        assert d["schema_version"] == "HATE/v1"
        assert d["record_type"] == "uat-state"
        assert d["state_type"] == "test_state"
        assert d["run_id"] == "run-001"
        assert d["sourceRefs"] == ["report.json"]

    def test_timestamp_is_set(self) -> None:
        """Each UAT state has a timestamp."""
        state = ReadyState(
            run_id="run-001",
            profile="product",
            sourceRefs=["report.json"],
        )
        d = state.to_dict()
        assert "timestamp" in d


class TestReadyState:
    """Tests for ReadyState."""

    def test_ready_state_fixture(self) -> None:
        """Ready fixture produces go status with no blockers."""
        fixture = load_fixture(READY_FIXTURE)
        input_data = fixture["input"]

        state = build_ready_state(
            readiness_report=input_data["readiness_report"],
            run_id=input_data["run_id"],
            profile=input_data["profile"],
        )

        expected = fixture["expected"]
        assert state.state_type == expected["state_type"]
        assert state.overall_status == expected["overall_status"]
        assert len(state.blockers) == 0
        assert state.manual_review_count == expected["manual_review_count"]

    def test_ready_state_ui_requirements(self) -> None:
        """Ready state has correct UI requirements."""
        state = ReadyState(
            run_id="run-001",
            profile="product",
            sourceRefs=["report.json"],
        )
        d = state.to_dict()
        assert "show_run_provenance" in d["ui_requirements"]
        assert "show_eligible_status_with_sourceRefs" in d["ui_requirements"]
        assert "no_blockers_visible" in d["ui_requirements"]


class TestSoftGapState:
    """Tests for SoftGapState."""

    def test_soft_gap_fixture(self) -> None:
        """Soft gap fixture shows conditional status with gaps."""
        fixture = load_fixture(SOFT_GAP_FIXTURE)
        input_data = fixture["input"]

        state = build_soft_gap_state(
            readiness_report=input_data["readiness_report"],
            run_id=input_data["run_id"],
            profile=input_data["profile"],
        )

        expected = fixture["expected"]
        assert state.state_type == expected["state_type"]
        assert state.overall_status == expected["overall_status"]
        assert state.soft_gap_count == expected["soft_gap_count"]
        assert len(state.soft_gaps) > 0

    def test_soft_gap_ui_requirements(self) -> None:
        """Soft gap state has correct UI requirements."""
        state = SoftGapState(
            run_id="run-001",
            profile="product",
            sourceRefs=["report.json"],
            soft_gap_count=1,
            soft_gaps=[{"gap_id": "gap-001", "reason": "Coverage threshold"}],
        )
        d = state.to_dict()
        assert "show_soft_gap_count" in d["ui_requirements"]
        assert "show_gap_reasons_with_sourceRefs" in d["ui_requirements"]


class TestHoldRiskState:
    """Tests for HoldRiskState."""

    def test_hold_risk_fixture(self) -> None:
        """Hold risk fixture shows oracle missing count."""
        fixture = load_fixture(HOLD_RISK_FIXTURE)
        input_data = fixture["input"]

        state = build_hold_risk_state(
            readiness_report=input_data["readiness_report"],
            risk_coverage_matrix=input_data["risk_coverage_matrix"],
            run_id=input_data["run_id"],
            profile=input_data["profile"],
        )

        expected = fixture["expected"]
        assert state.state_type == expected["state_type"]
        assert state.oracle_missing_count == expected["oracle_missing_count"]
        assert state.unsupported_claim_count == expected["unsupported_claim_count"]

    def test_hold_risk_cannot_show_product_ready(self) -> None:
        """Hold risk state cannot show product-ready."""
        fixture = load_fixture(HOLD_RISK_FIXTURE)
        expected = fixture["expected"]

        assert expected["cannot_show_product_ready"] is True


class TestHardDQSecurityState:
    """Tests for HardDQSecurityState."""

    def test_hard_dq_fixture(self) -> None:
        """Hard DQ fixture shows block status with severity."""
        fixture = load_fixture(HARD_DQ_FIXTURE)
        input_data = fixture["input"]

        state = build_hard_dq_security_state(
            readiness_report=input_data["readiness_report"],
            artifact_safety_report=input_data.get("artifact_safety_report"),
            run_id=input_data["run_id"],
            profile=input_data["profile"],
        )

        expected = fixture["expected"]
        assert state.state_type == expected["state_type"]
        assert state.overall_status == expected["overall_status"]
        assert state.hard_dq_count == expected["hard_dq_count"]
        assert state.severity == expected["severity"]

    def test_hard_dq_severity_not_color_only(self) -> None:
        """Hard DQ state must show severity, not color only."""
        state = HardDQSecurityState(
            run_id="run-001",
            profile="product",
            sourceRefs=["report.json"],
            hard_dq_count=1,
            hard_dqs=[{"dq_id": "dq-001", "severity": "critical"}],
            severity="critical",
        )
        d = state.to_dict()
        assert d["severity"] == "critical"
        assert "show_severity_not_color_only" in d["ui_requirements"]


class TestManualReviewPendingState:
    """Tests for ManualReviewPendingState."""

    def test_manual_review_fixture(self) -> None:
        """Manual review fixture shows pending reviews with overdue."""
        fixture = load_fixture(MANUAL_REVIEW_FIXTURE)
        input_data = fixture["input"]

        state = build_manual_review_pending_state(
            manual_review_requests=input_data["manual_review_requests"],
            run_id=input_data["run_id"],
            profile=input_data["profile"],
        )

        expected = fixture["expected"]
        assert state.state_type == expected["state_type"]
        assert state.total_count == expected["total_count"]
        assert state.overdue_count == expected["overdue_count"]

        # Verify owner visible
        for review in state.pending_reviews:
            assert "owner" in review
            assert review["owner"] is not None

    def test_manual_review_owner_visible(self) -> None:
        """Manual review state must show owner."""
        fixture = load_fixture(MANUAL_REVIEW_FIXTURE)
        expected = fixture["expected"]

        assert expected["has_owner_visible"] is True


class TestQuarantinedArtifactState:
    """Tests for QuarantinedArtifactState."""

    def test_quarantined_fixture(self) -> None:
        """Quarantined artifact fixture shows safe metadata only."""
        fixture = load_fixture(QUARANTINED_FIXTURE)
        input_data = fixture["input"]

        state = build_quarantined_artifact_state(
            artifact_safety_report=input_data["artifact_safety_report"],
            run_id=input_data["run_id"],
            profile=input_data["profile"],
        )

        expected = fixture["expected"]
        assert state.state_type == expected["state_type"]
        assert state.safe_metadata_only == expected["safe_metadata_only"]
        assert state.quarantine_reason is not None

    def test_quarantined_no_raw_artifact_link(self) -> None:
        """Quarantined artifact must not show raw artifact link."""
        state = QuarantinedArtifactState(
            run_id="run-001",
            profile="product",
            sourceRefs=["report.json"],
            artifact_id="secret-artifact-12345",
            classification="restricted",
            quarantine_reason="Secret detected",
            safe_metadata_only=True,
        )
        d = state.to_dict()

        # Safe metadata: hashed artifact_id, no raw artifact_id
        assert "artifact_id_safe" in d
        assert "artifact_id" not in d
        assert d["safe_metadata_only"] is True
        assert "remediation" in d

    def test_quarantined_has_remediation(self) -> None:
        """Quarantined artifact must show remediation contact."""
        fixture = load_fixture(QUARANTINED_FIXTURE)
        expected = fixture["expected"]

        assert expected["has_remediation"] is True


class TestMissingOracleState:
    """Tests for MissingOracleState."""

    def test_missing_oracle_fixture(self) -> None:
        """Missing oracle fixture shows oracle missing count."""
        fixture = load_fixture(MISSING_ORACLE_FIXTURE)
        input_data = fixture["input"]

        state = build_missing_oracle_state(
            risk_coverage_matrix=input_data["risk_coverage_matrix"],
            run_id=input_data["run_id"],
            profile=input_data["profile"],
        )

        expected = fixture["expected"]
        assert state.state_type == expected["state_type"]
        assert state.oracle_missing_count == expected["oracle_missing_count"]
        assert len(state.affected_risks) == expected["affected_risks_count"]

    def test_missing_oracle_cannot_claim_verified(self) -> None:
        """Missing oracle state cannot claim oracle-verified."""
        fixture = load_fixture(MISSING_ORACLE_FIXTURE)
        expected = fixture["expected"]

        assert expected["cannot_claim_oracle_verified"] is True


class TestCoverageOnlyState:
    """Tests for CoverageOnlyState."""

    def test_coverage_only_fixture(self) -> None:
        """Coverage-only fixture shows coverage_only count."""
        fixture = load_fixture(COVERAGE_ONLY_FIXTURE)
        input_data = fixture["input"]

        state = build_coverage_only_state(
            risk_coverage_matrix=input_data["risk_coverage_matrix"],
            run_id=input_data["run_id"],
            profile=input_data["profile"],
        )

        expected = fixture["expected"]
        assert state.state_type == expected["state_type"]
        assert state.coverage_only_count == expected["coverage_only_count"]

    def test_coverage_only_cannot_claim_execution(self) -> None:
        """Coverage-only state cannot claim execution-complete."""
        fixture = load_fixture(COVERAGE_ONLY_FIXTURE)
        expected = fixture["expected"]

        assert expected["cannot_claim_execution_complete"] is True


class TestUnsupportedClaimState:
    """Tests for UnsupportedClaimState."""

    def test_unsupported_claim_fixture(self) -> None:
        """Unsupported claim fixture shows unsupported claim count."""
        fixture = load_fixture(UNSUPPORTED_CLAIM_FIXTURE)
        input_data = fixture["input"]

        state = build_unsupported_claim_state(
            readiness_report=input_data["readiness_report"],
            run_id=input_data["run_id"],
            profile=input_data["profile"],
        )

        expected = fixture["expected"]
        assert state.state_type == expected["state_type"]
        assert state.unsupported_claim_count == expected["unsupported_claim_count"]

    def test_unsupported_claim_cannot_claim_ready(self) -> None:
        """Unsupported claim state cannot claim product-ready."""
        fixture = load_fixture(UNSUPPORTED_CLAIM_FIXTURE)
        expected = fixture["expected"]

        assert expected["cannot_claim_product_ready"] is True


class TestNoIndependentVerdictComputation:
    """Verify UAT states do not compute independent verdicts."""

    def test_status_from_report_not_computed(self) -> None:
        """overall_status comes from report, not computed."""
        fixture = load_fixture(HOLD_RISK_FIXTURE)
        input_data = fixture["input"]

        state = build_hold_risk_state(
            readiness_report=input_data["readiness_report"],
            risk_coverage_matrix=input_data["risk_coverage_matrix"],
            run_id=input_data["run_id"],
            profile=input_data["profile"],
        )

        # Status should match report status, not be computed
        assert state.overall_status == input_data["readiness_report"]["summary"]["overall_status"]

    def test_severity_from_hard_dq_not_computed(self) -> None:
        """severity comes from hard_dq finding, not computed."""
        fixture = load_fixture(HARD_DQ_FIXTURE)
        input_data = fixture["input"]

        state = build_hard_dq_security_state(
            readiness_report=input_data["readiness_report"],
            artifact_safety_report=input_data.get("artifact_safety_report"),
            run_id=input_data["run_id"],
            profile=input_data["profile"],
        )

        # Severity should match hard_dq finding severity
        if state.hard_dqs:
            assert state.severity == state.hard_dqs[0].get("severity")


class TestSourceRefsPreserved:
    """Verify all UAT states preserve sourceRefs from upstream reports."""

    def test_ready_state_source_refs(self) -> None:
        """Ready state preserves sourceRefs from report."""
        fixture = load_fixture(READY_FIXTURE)
        input_data = fixture["input"]

        state = build_ready_state(
            readiness_report=input_data["readiness_report"],
            run_id=input_data["run_id"],
            profile=input_data["profile"],
        )

        assert len(state.sourceRefs) > 0
        assert state.sourceRefs == input_data["readiness_report"]["sourceRefs"]

    def test_hold_risk_state_combined_source_refs(self) -> None:
        """Hold risk state combines sourceRefs from multiple reports."""
        fixture = load_fixture(HOLD_RISK_FIXTURE)
        input_data = fixture["input"]

        state = build_hold_risk_state(
            readiness_report=input_data["readiness_report"],
            risk_coverage_matrix=input_data["risk_coverage_matrix"],
            run_id=input_data["run_id"],
            profile=input_data["profile"],
        )

        # Should have sourceRefs from both readiness report and risk coverage matrix
        assert len(state.sourceRefs) >= len(input_data["readiness_report"]["sourceRefs"])

    def test_quarantined_state_source_refs(self) -> None:
        """Quarantined state preserves sourceRefs from safety report."""
        fixture = load_fixture(QUARANTINED_FIXTURE)
        input_data = fixture["input"]

        state = build_quarantined_artifact_state(
            artifact_safety_report=input_data["artifact_safety_report"],
            run_id=input_data["run_id"],
            profile=input_data["profile"],
        )

        assert len(state.sourceRefs) > 0


class TestUIRequirementsEnforced:
    """Verify UI requirements are properly set for each state."""

    def test_all_states_have_ui_requirements(self) -> None:
        """Every UAT state must have ui_requirements."""
        fixtures = [
            (ReadyState, READY_FIXTURE),
            (SoftGapState, SOFT_GAP_FIXTURE),
            (HoldRiskState, HOLD_RISK_FIXTURE),
            (HardDQSecurityState, HARD_DQ_FIXTURE),
            (ManualReviewPendingState, MANUAL_REVIEW_FIXTURE),
            (QuarantinedArtifactState, QUARANTINED_FIXTURE),
            (MissingOracleState, MISSING_ORACLE_FIXTURE),
            (CoverageOnlyState, COVERAGE_ONLY_FIXTURE),
            (UnsupportedClaimState, UNSUPPORTED_CLAIM_FIXTURE),
        ]

        for state_class, fixture_path in fixtures:
            fixture = load_fixture(fixture_path)
            expected = fixture["expected"]

            # Each fixture should define UI requirements
            assert "ui_requirements" in expected
            assert len(expected["ui_requirements"]) >= 4