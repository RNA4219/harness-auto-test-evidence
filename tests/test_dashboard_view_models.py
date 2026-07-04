"""Tests for HATE Dashboard View Models.

Dashboard view models are projections from reports, not independent verdict computation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

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


# Fixture paths
FIXTURE_DIR = Path("fixtures/dashboard/view-models")
ROOT = Path(__file__).resolve().parents[1]
READY_RUN_FIXTURE = FIXTURE_DIR / "ready-run" / "fixture.json"
HOLD_ORACLE_FIXTURE = FIXTURE_DIR / "hold-risk-without-oracle" / "fixture.json"
QUARANTINED_FIXTURE = FIXTURE_DIR / "quarantined-artifact" / "fixture.json"
MANUAL_REVIEW_FIXTURE = FIXTURE_DIR / "manual-review-pending" / "fixture.json"
MISSING_REPORT_FIXTURE = FIXTURE_DIR / "missing-report" / "fixture.json"


def load_fixture(path: Path) -> dict:
    """Load fixture JSON."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class TestCanonicalFixturePaths:
    """Verify all fixture paths exist and have expected structure."""

    def test_all_fixture_paths_exist(self) -> None:
        """All 5 fixture paths must exist."""
        assert READY_RUN_FIXTURE.exists()
        assert HOLD_ORACLE_FIXTURE.exists()
        assert QUARANTINED_FIXTURE.exists()
        assert MANUAL_REVIEW_FIXTURE.exists()
        assert MISSING_REPORT_FIXTURE.exists()

    def test_fixtures_have_description(self) -> None:
        """Each fixture must have a description field."""
        for path in [
            READY_RUN_FIXTURE,
            HOLD_ORACLE_FIXTURE,
            QUARANTINED_FIXTURE,
            MANUAL_REVIEW_FIXTURE,
            MISSING_REPORT_FIXTURE,
        ]:
            fixture = load_fixture(path)
            assert "description" in fixture
            assert "input" in fixture
            assert "expected" in fixture


class TestRunOverviewViewModel:
    """Tests for RunOverviewViewModel."""

    def test_to_dict_contains_required_fields(self) -> None:
        """to_dict must contain all required fields."""
        view = RunOverviewViewModel(
            run_id="run-001",
            profile="product",
            overall_status="go",
            hard_dq_count=0,
            soft_gap_count=1,
            unsupported_claim_count=0,
            manual_review_count=0,
            quarantined_artifact_count=0,
            missing_report_count=0,
            sourceRefs=["report.json"],
            blockers=[],
            next_actions=[],
        )
        d = view.to_dict()
        assert d["schema_version"] == "HATE/v1"
        assert d["record_type"] == "run-overview-view-model"
        assert d["run_id"] == "run-001"
        assert d["overall_status"] == "go"
        assert d["sourceRefs"] == ["report.json"]

    def test_is_ready_true_for_go_status(self) -> None:
        """is_ready returns True when status is go and no blockers."""
        view = RunOverviewViewModel(
            run_id="run-001",
            profile="product",
            overall_status="go",
            hard_dq_count=0,
            soft_gap_count=0,
            unsupported_claim_count=0,
            manual_review_count=0,
            quarantined_artifact_count=0,
            missing_report_count=0,
            sourceRefs=["report.json"],
            blockers=[],
            next_actions=[],
        )
        assert view.is_ready() is True

    def test_is_ready_false_for_block_status(self) -> None:
        """is_ready returns False when status is not go."""
        view = RunOverviewViewModel(
            run_id="run-001",
            profile="product",
            overall_status="block",
            hard_dq_count=1,
            soft_gap_count=0,
            unsupported_claim_count=0,
            manual_review_count=0,
            quarantined_artifact_count=0,
            missing_report_count=0,
            sourceRefs=["report.json"],
            blockers=[{"type": "hard_dq", "reason": "Test failure"}],
            next_actions=[],
        )
        assert view.is_ready() is False

    def test_is_ready_false_for_missing_report(self) -> None:
        """is_ready returns False when missing report count > 0."""
        view = RunOverviewViewModel(
            run_id="run-001",
            profile="product",
            overall_status="go",
            hard_dq_count=0,
            soft_gap_count=0,
            unsupported_claim_count=0,
            manual_review_count=0,
            quarantined_artifact_count=0,
            missing_report_count=1,
            sourceRefs=["report.json"],
            blockers=[],
            next_actions=[],
        )
        assert view.is_ready() is False

    def test_ready_run_fixture(self) -> None:
        """Ready run fixture produces go status view model."""
        fixture = load_fixture(READY_RUN_FIXTURE)
        input_data = fixture["input"]

        view = build_run_overview_view_model(
            readiness_report=input_data["readiness_report"],
            run_id=input_data["run_id"],
            profile=input_data["profile"],
            artifact_safety_reports=input_data.get("artifact_safety_reports"),
            manual_review_requests=input_data.get("manual_review_requests"),
            missing_reports=input_data.get("missing_reports"),
        )

        expected = fixture["expected"]
        assert view.overall_status == expected["overall_status"]
        assert view.is_ready() == expected["is_ready"]
        assert view.hard_dq_count == expected["hard_dq_count"]
        assert view.missing_report_count == expected["missing_report_count"]
        assert len(view.blockers) == 0

    def test_missing_report_fixture(self) -> None:
        """Missing report fixture produces block status with missing report blockers."""
        fixture = load_fixture(MISSING_REPORT_FIXTURE)
        input_data = fixture["input"]

        view = build_run_overview_view_model(
            readiness_report=input_data["readiness_report"],
            run_id=input_data["run_id"],
            profile=input_data["profile"],
            artifact_safety_reports=input_data.get("artifact_safety_reports"),
            manual_review_requests=input_data.get("manual_review_requests"),
            missing_reports=input_data.get("missing_reports"),
        )

        expected = fixture["expected"]
        assert view.overall_status == expected["overall_status"]
        assert view.is_ready() == expected["is_ready"]
        assert view.missing_report_count == expected["missing_report_count"]
        assert len(view.blockers) == expected["missing_report_count"]

        # Verify blocker types
        blocker_types = [b["type"] for b in view.blockers]
        assert all(t in expected["missing_report_blocker_types"] for t in blocker_types)


class TestArtifactSafetyViewModel:
    """Tests for ArtifactSafetyViewModel."""

    def test_to_dict_safe_metadata_for_quarantined(self) -> None:
        """Quarantined artifact shows safe metadata only (hashed id)."""
        view = ArtifactSafetyViewModel(
            artifact_id="secret-artifact-12345",
            classification="restricted",
            quarantine_status="quarantined",
            redaction_status="required",
            safe_metadata_only=True,
            quarantine_reason="Secret detected",
            sourceRefs=["safety-report.json"],
        )
        d = view.to_dict()

        # Safe metadata only: artifact_id_safe (hashed), no raw artifact_id
        assert "artifact_id_safe" in d
        assert "artifact_id" not in d  # Raw ID should not be present
        assert d["safe_metadata_only"] is True
        assert d["quarantine_reason"] == "Secret detected"
        assert d["remediation"] == "Contact security team for quarantine review"

    def test_to_dict_full_metadata_for_safe_artifact(self) -> None:
        """Safe artifact shows full metadata with artifact_id."""
        view = ArtifactSafetyViewModel(
            artifact_id="safe-artifact-001",
            classification="public",
            quarantine_status="none",
            redaction_status="not_required",
            safe_metadata_only=False,
            quarantine_reason=None,
            sourceRefs=["safety-report.json"],
        )
        d = view.to_dict()

        # Full metadata: artifact_id visible
        assert d["artifact_id"] == "safe-artifact-001"
        assert "artifact_id_safe" not in d
        assert d["safe_metadata_only"] is False
        assert d["quarantine_status"] == "none"

    def test_quarantined_artifact_fixture(self) -> None:
        """Quarantined artifact fixture produces safe metadata view."""
        fixture = load_fixture(QUARANTINED_FIXTURE)
        input_data = fixture["input"]

        view = build_artifact_safety_view_model(input_data["artifact_safety_report"])

        expected = fixture["expected"]
        assert view.quarantine_status == expected["quarantine_status"]
        assert view.safe_metadata_only == expected["safe_metadata_only"]
        assert view.quarantine_reason is not None  # Has quarantine reason

        d = view.to_dict()
        # Verify no raw artifact_id for quarantined
        if expected["no_raw_artifact_id"]:
            assert "artifact_id" not in d or d.get("safe_metadata_only") is True
        assert "artifact_id_safe" in d  # Safe hashed ID
        assert "remediation" in d  # Has remediation


class TestManualReviewQueueViewModel:
    """Tests for ManualReviewQueueViewModel."""

    def test_to_dict_contains_required_fields(self) -> None:
        """to_dict must contain all required fields."""
        view = ManualReviewQueueViewModel(
            pending_reviews=[
                {"review_id": "review-001", "owner": "owner@example.com", "status": "pending"}
            ],
            total_count=1,
            overdue_count=0,
            sourceRefs=["review-request.json"],
        )
        d = view.to_dict()
        assert d["schema_version"] == "HATE/v1"
        assert d["record_type"] == "manual-review-queue-view-model"
        assert d["total_count"] == 1
        assert len(d["pending_reviews"]) == 1

    def test_manual_review_pending_fixture(self) -> None:
        """Manual review fixture shows pending reviews with overdue flag."""
        fixture = load_fixture(MANUAL_REVIEW_FIXTURE)
        input_data = fixture["input"]

        view = build_manual_review_queue_view_model(input_data["manual_review_requests"])

        expected = fixture["expected"]
        assert view.total_count == expected["total_count"]
        assert view.overdue_count == expected["overdue_count"]
        assert len(view.pending_reviews) == expected["pending_reviews_count"]

        # Verify owner visible
        for review in view.pending_reviews:
            assert "owner" in review
            assert review["owner"] is not None

        # Verify overdue flag
        overdue_reviews = [r for r in view.pending_reviews if r["is_overdue"]]
        assert len(overdue_reviews) == expected["overdue_count"]


class TestRiskCoverageViewModel:
    """Tests for RiskCoverageViewModel."""

    def test_to_dict_contains_required_fields(self) -> None:
        """to_dict must contain all required fields."""
        view = RiskCoverageViewModel(
            risk_count=10,
            covered_count=8,
            uncovered_count=2,
            oracle_missing_count=1,
            coverage_only_count=0,
            high_severity_uncovered=[],
            sourceRefs=["risk-matrix.json"],
        )
        d = view.to_dict()
        assert d["schema_version"] == "HATE/v1"
        assert d["record_type"] == "risk-coverage-view-model"
        assert d["risk_count"] == 10
        assert d["oracle_missing_count"] == 1

    def test_hold_oracle_fixture(self) -> None:
        """Hold oracle fixture shows oracle missing count."""
        fixture = load_fixture(HOLD_ORACLE_FIXTURE)
        input_data = fixture["input"]

        view = build_risk_coverage_view_model(input_data["risk_coverage_matrix"])

        expected = fixture["expected"]
        assert view.oracle_missing_count == expected["oracle_missing_count"]
        assert len(view.high_severity_uncovered) == expected["high_severity_uncovered_count"]


class TestDashboardViewModel:
    """Tests for combined DashboardViewModel."""

    def test_to_dict_contains_all_views(self) -> None:
        """Dashboard to_dict contains run_overview, artifact_safety, etc."""
        run_view = RunOverviewViewModel(
            run_id="run-001",
            profile="product",
            overall_status="go",
            hard_dq_count=0,
            soft_gap_count=0,
            unsupported_claim_count=0,
            manual_review_count=0,
            quarantined_artifact_count=0,
            missing_report_count=0,
            sourceRefs=["report.json"],
            blockers=[],
            next_actions=[],
        )

        artifact_view = ArtifactSafetyViewModel(
            artifact_id="artifact-001",
            classification="public",
            quarantine_status="none",
            redaction_status="not_required",
            safe_metadata_only=False,
            quarantine_reason=None,
            sourceRefs=["safety.json"],
        )

        dashboard = DashboardViewModel(
            run_overview=run_view,
            artifact_safety=[artifact_view],
            manual_review_queue=None,
            risk_coverage=None,
        )

        d = dashboard.to_dict()
        assert "run_overview" in d
        assert "artifact_safety" in d
        assert len(d["artifact_safety"]) == 1
        assert d["schema_version"] == "HATE/v1"

    def test_build_dashboard_from_reports(self) -> None:
        """build_dashboard_view_model aggregates from reports."""
        fixture = load_fixture(READY_RUN_FIXTURE)
        input_data = fixture["input"]

        dashboard = build_dashboard_view_model(
            readiness_report=input_data["readiness_report"],
            run_id=input_data["run_id"],
            profile=input_data["profile"],
            artifact_safety_reports=input_data.get("artifact_safety_reports"),
            manual_review_requests=input_data.get("manual_review_requests"),
            missing_reports=input_data.get("missing_reports"),
        )

        expected = fixture["expected"]
        assert dashboard.run_overview.overall_status == expected["overall_status"]
        assert dashboard.run_overview.is_ready() == expected["is_ready"]

    def test_view_model_record_types_are_registered_and_schema_compatible(self) -> None:
        """All emitted dashboard view-model records are registered with schema coverage."""
        fixture = load_fixture(READY_RUN_FIXTURE)
        input_data = fixture["input"]
        dashboard = build_dashboard_view_model(
            readiness_report=input_data["readiness_report"],
            run_id=input_data["run_id"],
            profile=input_data["profile"],
            artifact_safety_reports=input_data.get("artifact_safety_reports"),
            manual_review_requests=input_data.get("manual_review_requests"),
            missing_reports=input_data.get("missing_reports"),
        ).to_dict()
        manual_queue = ManualReviewQueueViewModel(
            pending_reviews=[],
            total_count=0,
            overdue_count=0,
            sourceRefs=["manual-review://empty"],
        ).to_dict()
        risk_coverage = RiskCoverageViewModel(
            risk_count=0,
            covered_count=0,
            uncovered_count=0,
            oracle_missing_count=0,
            coverage_only_count=0,
            high_severity_uncovered=[],
            sourceRefs=["risk://empty"],
        ).to_dict()
        records = [
            dashboard,
            dashboard["run_overview"],
            *dashboard["artifact_safety"],
            manual_queue,
            risk_coverage,
        ]
        registry = json.loads((ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json").read_text(encoding="utf-8"))
        by_record_type = {record["record_type"]: record for record in registry["records"]}

        for record in records:
            assert record["record_type"] in by_record_type
            schema_path = ROOT / by_record_type[record["record_type"]]["schema"]
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            assert set(schema["required"]) <= set(record)
            assert record["record_type"] in schema["properties"]["record_type"]["enum"]


class TestNoIndependentVerdictComputation:
    """Verify view models do not compute independent verdicts."""

    def test_status_from_report_not_computed(self) -> None:
        """overall_status comes from report, not computed."""
        fixture = load_fixture(MISSING_REPORT_FIXTURE)
        input_data = fixture["input"]

        view = build_run_overview_view_model(
            readiness_report=input_data["readiness_report"],
            run_id=input_data["run_id"],
            profile=input_data["profile"],
            missing_reports=input_data.get("missing_reports"),
        )

        # Status should match report status, not be computed from missing_reports
        assert view.overall_status == input_data["readiness_report"]["summary"]["overall_status"]

    def test_product_ready_forbidden_when_missing_report(self) -> None:
        """Product-ready forbidden when missing_report_count > 0."""
        fixture = load_fixture(MISSING_REPORT_FIXTURE)
        expected = fixture["expected"]

        assert expected["cannot_show_product_ready"] is True
        assert expected["is_ready"] is False


class TestSourceRefsVisible:
    """Verify all blockers have sourceRefs linking to report evidence."""

    def test_blockers_have_source_ref(self) -> None:
        """Blockers must link to sourceRefs for traceability."""
        fixture = load_fixture(MISSING_REPORT_FIXTURE)
        input_data = fixture["input"]

        view = build_run_overview_view_model(
            readiness_report=input_data["readiness_report"],
            run_id=input_data["run_id"],
            profile=input_data["profile"],
            missing_reports=input_data.get("missing_reports"),
        )

        for blocker in view.blockers:
            assert "sourceRef" in blocker
            # sourceRef should point to view_models.py code or report
            assert blocker["sourceRef"] is not None

    def test_view_model_has_source_refs(self) -> None:
        """View model must have sourceRefs from report."""
        fixture = load_fixture(READY_RUN_FIXTURE)
        input_data = fixture["input"]

        view = build_run_overview_view_model(
            readiness_report=input_data["readiness_report"],
            run_id=input_data["run_id"],
            profile=input_data["profile"],
        )

        assert len(view.sourceRefs) > 0
        assert view.sourceRefs == input_data["readiness_report"]["sourceRefs"]


class TestNextActions:
    """Verify next_actions are actionable with commands/links."""

    def test_next_actions_for_blocked_run(self) -> None:
        """Blocked run should have next_actions with commands."""
        fixture = load_fixture(MISSING_REPORT_FIXTURE)
        input_data = fixture["input"]

        view = build_run_overview_view_model(
            readiness_report=input_data["readiness_report"],
            run_id=input_data["run_id"],
            profile=input_data["profile"],
            missing_reports=input_data.get("missing_reports"),
        )

        # Should have next actions for missing reports
        assert len(view.next_actions) > 0

        for action in view.next_actions:
            assert "action" in action
            assert "label" in action
            assert "link" in action

    def test_no_next_actions_for_ready_run(self) -> None:
        """Ready run should have no next_actions (nothing to do)."""
        fixture = load_fixture(READY_RUN_FIXTURE)
        input_data = fixture["input"]

        view = build_run_overview_view_model(
            readiness_report=input_data["readiness_report"],
            run_id=input_data["run_id"],
            profile=input_data["profile"],
            missing_reports=input_data.get("missing_reports"),
        )

        expected = fixture["expected"]
        if expected["is_ready"]:
            # Ready run has no blockers and no next_actions for blockers
            assert len(view.next_actions) == 0
