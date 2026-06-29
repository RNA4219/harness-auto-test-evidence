"""Tests for mock abuse and assertion quality detector - HATE-PG-004B.

Per EPIC_TASK_PACKETS.md test requirements:
- Boundary mock allowed
- Internal function mock flagged
- Empty stub flagged
- Assert-no-exception-only flagged
- Constant assertion flagged
- Snapshot-only soft gap/hold by profile
- Semantic assertion accepted
- No-oracle risk hold
- False-positive suppression with owner/expiry
"""

import json
import pytest
from pathlib import Path

from hate.test_integrity.mock_assertion import (
    AssertionClassification,
    AssertionFinding,
    MockClassification,
    MockFinding,
    TestIntegrityReport,
    build_test_integrity_report,
    classify_assertion,
    classify_mock,
    detect_assertion_quality_signals,
    detect_empty_stub,
    detect_mock_abuse_signals,
    has_domain_oracle,
)
from hate.test_integrity.models import IntegritySignalType


FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "test-integrity" / "mock-assertion"


@pytest.fixture
def load_fixture():
    """Pytest fixture to load fixture files."""
    def _load(fixture_name: str) -> dict:
        """Load a fixture file."""
        fixture_path = FIXTURE_DIR / fixture_name / "fixture.json"
        # Missing fixture must FAIL, not skip
        assert fixture_path.exists(), f"Required fixture missing: {fixture_path}"
        with open(fixture_path) as f:
            return json.load(f)
    return _load


class TestMockClassification:
    """Tests for mock classification logic."""

    def test_external_boundary_http_mock_allowed(self):
        """Boundary mock allowed - HTTP/network mock is legitimate."""
        classification = classify_mock("http_client", "mock network request")
        assert classification == MockClassification.EXTERNAL_BOUNDARY

    def test_external_boundary_filesystem_mock_allowed(self):
        """Boundary mock allowed - filesystem mock is legitimate."""
        classification = classify_mock("file_handler", "mock filesystem access")
        assert classification == MockClassification.EXTERNAL_BOUNDARY

    def test_external_boundary_clock_mock_allowed(self):
        """Boundary mock allowed - clock/time mock is legitimate."""
        classification = classify_mock("datetime_service", "mock time for testing")
        assert classification == MockClassification.EXTERNAL_BOUNDARY

    def test_internal_domain_service_mock_flagged(self):
        """Internal function mock flagged - mocking service logic."""
        classification = classify_mock("UserService", "mock service logic")
        assert classification == MockClassification.INTERNAL_DOMAIN

    def test_internal_domain_handler_mock_flagged(self):
        """Internal function mock flagged - mocking handler."""
        classification = classify_mock("RequestHandler", "mock handler behavior")
        assert classification == MockClassification.INTERNAL_DOMAIN

    def test_internal_domain_calculator_mock_flagged(self):
        """Internal function mock flagged - mocking calculator."""
        classification = classify_mock("Calculator", "mock calculator")
        assert classification == MockClassification.INTERNAL_DOMAIN


class TestEmptyStubDetection:
    """Tests for empty stub detection."""

    def test_pass_is_empty_stub(self):
        """Empty stub flagged - pass statement."""
        assert detect_empty_stub("def foo(): pass")

    def test_ellipsis_is_empty_stub(self):
        """Empty stub flagged - ellipsis."""
        assert detect_empty_stub("def foo(): ...")

    def test_return_none_is_empty_stub(self):
        """Empty stub flagged - returning None."""
        assert detect_empty_stub("return_value = None")

    def test_mock_without_behavior_is_empty_stub(self):
        """Empty stub flagged - bare Mock()."""
        assert detect_empty_stub("Mock()")

    def test_mock_with_return_value_not_empty(self):
        """Mock with behavior is not empty stub."""
        assert not detect_empty_stub("Mock(return_value=42)")

    def test_mock_with_side_effect_not_empty(self):
        """Mock with side effect is not empty stub."""
        assert not detect_empty_stub("Mock(side_effect=lambda x: x + 1)")


class TestAssertionClassification:
    """Tests for assertion quality classification."""

    def test_constant_true_is_trivial(self):
        """Constant assertion flagged - assert True."""
        classification = classify_assertion("assert True")
        assert classification == AssertionClassification.TRIVIAL

    def test_constant_comparison_is_trivial(self):
        """Constant assertion flagged - assert 1 == 1."""
        classification = classify_assertion("assert 1 == 1")
        assert classification == AssertionClassification.TRIVIAL

    def test_self_comparison_is_constant(self):
        """Constant assertion flagged - assert x == x."""
        classification = classify_assertion("assert result == result")
        assert classification == AssertionClassification.CONSTANT

    def test_snapshot_only_without_guard(self):
        """Snapshot-only soft gap/hold by profile."""
        classification = classify_assertion(
            "expect(component).toMatchSnapshot()",
            test_body="test('component') { render() }"
        )
        assert classification == AssertionClassification.SNAPSHOT_ONLY

    def test_snapshot_with_semantic_guard_is_meaningful(self):
        """Semantic assertion accepted - snapshot with guard."""
        classification = classify_assertion(
            "expect(button).toMatchSnapshot()",
            test_body="expect(button.getByRole('button')).toBeTruthy()"
        )
        assert classification == AssertionClassification.MEANINGFUL

    def test_domain_value_check_is_meaningful(self):
        """Domain assertion accepted - verifies expected value."""
        classification = classify_assertion("assert result.name == 'Alice'")
        assert classification == AssertionClassification.MEANINGFUL

    def test_empty_assertion_is_missing(self):
        """No assertion flagged as missing."""
        classification = classify_assertion("")
        assert classification == AssertionClassification.MISSING

    def test_no_exception_only_flagged(self):
        """Assert-no-exception-only flagged."""
        classification = classify_assertion("", "# just check it runs")
        assert classification == AssertionClassification.NO_EXCEPTION_ONLY


class TestDomainOracleDetection:
    """Tests for domain oracle detection."""

    def test_expected_value_is_domain_oracle(self):
        """Domain oracle - expected value check."""
        assert has_domain_oracle("assert result == expected")

    def test_comparison_is_domain_oracle(self):
        """Domain oracle - comparison check."""
        assert has_domain_oracle("assert result >= 10")

    def test_string_match_is_domain_oracle(self):
        """Domain oracle - string match."""
        assert has_domain_oracle("assert response.status == 'success'")

    def test_property_decorator_is_domain_oracle(self):
        """Domain oracle - property-based test."""
        assert has_domain_oracle("@given st.lists")

    def test_no_assertion_not_domain_oracle(self):
        """No oracle - no meaningful assertion."""
        assert not has_domain_oracle("def test(): pass")


class TestMockAbuseSignals:
    """Tests for mock abuse signal detection."""

    def test_boundary_mock_allowed(self, load_fixture):
        """Boundary mock allowed - fixture test."""
        fixture = load_fixture("boundary-mock-allowed")
        findings = detect_mock_abuse_signals([fixture])
        # External boundary mock should NOT generate findings
        assert len(findings) == 0

    def test_internal_function_mock_flagged(self, load_fixture):
        """Internal function mock flagged - fixture test."""
        fixture = load_fixture("overmocked-domain")
        findings = detect_mock_abuse_signals([fixture])
        assert len(findings) > 0
        assert any(f.classification == MockClassification.INTERNAL_DOMAIN for f in findings)

    def test_empty_stub_flagged(self, load_fixture):
        """Empty stub flagged - fixture test."""
        fixture = load_fixture("empty-stub")
        findings = detect_mock_abuse_signals([fixture])
        assert len(findings) > 0
        assert any(f.classification == MockClassification.EMPTY_STUB for f in findings)


class TestAssertionQualitySignals:
    """Tests for assertion quality signal detection."""

    def test_no_exception_only_flagged(self, load_fixture):
        """Assert-no-exception-only flagged."""
        fixture = load_fixture("no-assertions")
        findings = detect_assertion_quality_signals([fixture])
        assert len(findings) > 0
        assert any(f.assertion_type == AssertionClassification.NO_EXCEPTION_ONLY for f in findings)

    def test_constant_assertion_flagged(self, load_fixture):
        """Constant assertion flagged."""
        fixture = load_fixture("assert-true-constant")
        findings = detect_assertion_quality_signals([fixture])
        assert len(findings) > 0
        assert any(f.assertion_type == AssertionClassification.TRIVIAL for f in findings)

    def test_snapshot_only_soft_gap_default(self, load_fixture):
        """Snapshot-only soft gap/hold by profile - default profile."""
        fixture = load_fixture("snapshot-only")
        findings = detect_assertion_quality_signals([fixture])
        assert len(findings) > 0
        assert any(f.assertion_type == AssertionClassification.SNAPSHOT_ONLY for f in findings)

    def test_semantic_assertion_accepted(self, load_fixture):
        """Semantic assertion accepted."""
        fixture = load_fixture("snapshot-with-semantic-guard")
        findings = detect_assertion_quality_signals([fixture])
        # Semantic guard should NOT generate findings
        assert len(findings) == 0

    def test_no_oracle_hold(self, load_fixture):
        """No-oracle risk hold."""
        fixture = load_fixture("risk-without-oracle")
        findings = detect_assertion_quality_signals([fixture])
        assert len(findings) > 0
        assert any(f.assertion_type == AssertionClassification.MISSING for f in findings)


class TestBuildTestIntegrityReport:
    """Tests for full report generation."""

    def test_report_structure(self):
        """Report contains required fields."""
        sources = [
            {
                "test_id": "test_example",
                "code": "assert True",
                "language": "python",
                "framework": "pytest",
                "source_ref": "test:example",
                "mock_targets": [],
                "assertions": [{"text": "assert True", "line_number": 1}],
            }
        ]
        report = build_test_integrity_report(sources, profile="default")
        assert report.schema_version == "HATE/v1"
        assert report.record_type == "test_integrity_report"
        assert report.profile == "default"
        assert "overall_status" in report.summary
        assert "sourceRefs" in report.as_dict()

    def test_release_profile_snapshot_hold(self, load_fixture):
        """Snapshot-only hold in release/product profile."""
        fixture = load_fixture("snapshot-only")
        report = build_test_integrity_report([fixture], profile="release")
        # Release profile should have hold or blocked effect
        assert report.summary["overall_status"] in {"hold", "blocked"}

    def test_default_profile_snapshot_soft_gap(self, load_fixture):
        """Snapshot-only soft gap in default profile."""
        fixture = load_fixture("snapshot-only")
        report = build_test_integrity_report([fixture], profile="default")
        assert report.summary["overall_status"] in {"soft_gap", "pass"}

    def test_boundary_manifest_suppresses_false_positive(self, load_fixture):
        """False-positive suppression with owner/expiry - boundary manifest."""
        fixture = load_fixture("overmocked-domain")
        # If Calculator is declared in boundary manifest, it's not flagged
        report = build_test_integrity_report(
            [fixture],
            profile="default",
            boundary_manifest=["Calculator"]  # Declare as boundary
        )
        # Should reduce severity when declared
        for finding in report.findings:
            if finding["signal_id"] == IntegritySignalType.MOCK_ABUSE_DETECTED.value:
                assert finding["product_effect"]["decision_impact"] in {"soft_gap", "conditional"}

    def test_risk_debt_generated_for_blocking_findings(self):
        """Risk debt generated for hold/block findings."""
        sources = [
            {
                "test_id": "test_blocking",
                "code": "",
                "language": "python",
                "framework": "pytest",
                "source_ref": "test:blocking",
                "mock_targets": [
                    {
                        "target": "DomainService",
                        "context": "mock domain logic",
                        "mock_code": "Mock()",
                        "line_number": 1,
                    }
                ],
                "assertions": [],
            }
        ]
        report = build_test_integrity_report(sources, profile="release")
        assert len(report.risk_debt) > 0


class TestReportSerialization:
    """Tests for report serialization."""

    def test_as_dict_contains_all_fields(self):
        """Report as_dict contains all required fields."""
        sources = [
            {
                "test_id": "test_serialize",
                "code": "assert result == expected",
                "language": "python",
                "framework": "pytest",
                "source_ref": "test:serialize",
                "mock_targets": [],
                "assertions": [{"text": "assert result == expected", "line_number": 1}],
            }
        ]
        report = build_test_integrity_report(sources)
        report_dict = report.as_dict()
        assert "schema_version" in report_dict
        assert "record_type" in report_dict
        assert "fixture_id" in report_dict
        assert "profile" in report_dict
        assert "summary" in report_dict
        assert "mock_abuse_findings" in report_dict
        assert "assertion_quality_findings" in report_dict
        assert "findings" in report_dict
        assert "risk_debt" in report_dict
        assert "sourceRefs" in report_dict


class TestProfileEffects:
    """Tests for profile-based effects."""

    def test_default_profile_trivial_soft_gap(self):
        """Trivial assertion soft gap in default profile."""
        sources = [
            {
                "test_id": "test_trivial",
                "code": "assert True",
                "language": "python",
                "framework": "pytest",
                "source_ref": "test:trivial",
                "mock_targets": [],
                "assertions": [{"text": "assert True", "line_number": 1}],
            }
        ]
        report = build_test_integrity_report(sources, profile="default")
        assert report.summary["soft_gap_count"] > 0

    def test_release_profile_trivial_blocked(self):
        """Trivial assertion blocked in release profile."""
        sources = [
            {
                "test_id": "test_blocking",
                "code": "",
                "language": "python",
                "framework": "pytest",
                "source_ref": "test:blocking",
                "mock_targets": [],
                "assertions": [],
            }
        ]
        report = build_test_integrity_report(sources, profile="release")
        assert report.summary["blocked_count"] > 0 or report.summary["hold_count"] > 0


class TestConfidenceLevels:
    """Tests for confidence level assignment."""

    def test_internal_domain_high_confidence(self):
        """Internal domain mock has high confidence."""
        sources = [
            {
                "test_id": "test_confidence",
                "code": "",
                "language": "python",
                "framework": "pytest",
                "source_ref": "test:confidence",
                "mock_targets": [
                    {
                        "target": "DomainService",
                        "context": "mock domain logic",
                        "mock_code": "Mock()",
                        "line_number": 1,
                    }
                ],
                "assertions": [],
            }
        ]
        findings = detect_mock_abuse_signals(sources)
        internal_findings = [f for f in findings if f.classification == MockClassification.INTERNAL_DOMAIN]
        assert len(internal_findings) > 0
        assert internal_findings[0].confidence >= 0.8

    def test_empty_stub_high_confidence(self):
        """Empty stub has high confidence."""
        sources = [
            {
                "test_id": "test_stub",
                "code": "",
                "language": "python",
                "framework": "pytest",
                "source_ref": "test:stub",
                "mock_targets": [
                    {
                        "target": "service",
                        "context": "",
                        "mock_code": "Mock()",
                        "line_number": 1,
                    }
                ],
                "assertions": [],
            }
        ]
        findings = detect_mock_abuse_signals(sources)
        stub_findings = [f for f in findings if f.classification == MockClassification.EMPTY_STUB]
        assert len(stub_findings) > 0
        assert stub_findings[0].confidence >= 0.9


class TestFixtureNameCoupling:
    """Tests for test/fixture-name coupling detection."""

    def test_mock_returns_fixture_name_detected(self, load_fixture):
        """Mock returns fixture name - coupling detected."""
        fixture = load_fixture("mock-returns-fixture-name")
        findings = detect_mock_abuse_signals([fixture])
        # Should detect fixture-name coupling pattern
        assert len(findings) > 0
        # The mock returns the test name itself, creating coupling
        assert any("fixture" in f.reason.lower() or "coupling" in f.reason.lower() for f in findings)


class TestManualReviewDocumented:
    """Tests for manual review with documentation."""

    def test_manual_review_fields_visible(self, load_fixture):
        """Manual review documented - owner/expiry/sourceRef visible."""
        fixture = load_fixture("manual-review-documented")
        # Verify fixture contains required fields
        assert "owner" in fixture
        assert "expiry" in fixture
        assert "manual_review_required" in fixture
        assert fixture["owner"] == "test-team-lead@example.com"
        assert fixture["expiry"] == "2026-07-30"
        assert fixture["manual_review_required"] is True

    def test_manual_review_conditional_effect(self, load_fixture):
        """Manual review documented - conditional effect."""
        fixture = load_fixture("manual-review-documented")
        report = build_test_integrity_report([fixture], profile="default")
        # Manual review documentation should create conditional/soft_gap/hold effect
        # Note: Since fixture has no assertions, it may be blocked in stricter profiles
        assert report.summary["overall_status"] in {"soft_gap", "conditional", "hold", "blocked"}


class TestFixtureBuilderLegit:
    """Tests for legitimate fixture builder pattern."""

    def test_fixture_builder_legit_passes(self, load_fixture):
        """Fixture builder legit - no findings when not replacing oracle."""
        fixture = load_fixture("fixture-builder-legit")
        findings = detect_mock_abuse_signals([fixture])
        # Fixture builder is NOT mock abuse - it builds data, not behavior
        assert len(findings) == 0

    def test_fixture_builder_has_meaningful_assertion(self, load_fixture):
        """Fixture builder legit - still requires meaningful assertion."""
        fixture = load_fixture("fixture-builder-legit")
        findings = detect_assertion_quality_signals([fixture])
        # Should have meaningful assertion against system under test
        assert len(findings) == 0  # No quality issues


class TestCanonicalFixturePaths:
    """Tests for canonical fixture directory existence."""

    def test_all_canonical_fixture_paths_exist(self):
        """All required canonical fixture directories exist."""
        canonical_fixtures = [
            "strong-assertions",
            "boundary-mock-allowed",
            "manual-review-documented",
            "fixture-builder-legit",
            "no-assertions",
            "assertion-free-smoke",
            "overmocked-domain",
            "empty-stub-success",
            "mock-returns-fixture-name",
            "risk-without-oracle",
            # Legacy fixtures still in use
            "assert-true-constant",
            "empty-stub",
            "snapshot-only",
            "snapshot-with-semantic-guard",
            "property-assertion",
        ]
        for fixture_name in canonical_fixtures:
            fixture_path = FIXTURE_DIR / fixture_name / "fixture.json"
            assert fixture_path.exists(), f"Canonical fixture missing: {fixture_path}"