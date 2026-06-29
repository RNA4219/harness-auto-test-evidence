"""Tests for test coupling and manual review detector - HATE-PG-004C.

This module tests the coupling detector for:
- implementation_test_coupling detection
- risk_without_oracle detection
- coverage_without_evidence detection
- manual_review_required handling
- False positive guards (data-driven parser, stable fixture mapping)

Per HATE-PG-004C spec:
- 12+ test cases required
- No skip/focus markers to hide gaps
- All fixtures tested
"""

import json
from pathlib import Path

from hate.test_integrity.coupling import (
    CouplingClassification,
    OracleClassification,
    CoverageClassification,
    ManualReviewClassification,
    classify_coupling,
    classify_oracle,
    classify_coverage_evidence,
    detect_implementation_test_coupling,
    detect_risk_without_oracle,
    detect_coverage_without_evidence,
    build_coupling_integrity_report,
    DETECTOR_ID_COUPLING,
)
from hate.test_integrity.manual_review import (
    HumanRecord,
    classify_manual_review_requirement,
    generate_manual_review_request,
    process_manual_review_requests,
    check_human_record_expiry,
    integrate_manual_review_with_findings,
    REQUIRED_DECISION_TYPES,
)


# =============================================================================
# Test Coupling Classification
# =============================================================================

class TestCouplingClassification:
    """Tests for classify_coupling function."""

    def test_test_name_branch_detected(self):
        """Test detection of production code branching on test names."""
        code = """
def process(mode):
    if mode == 'test_unit_A':
        return 'test_behavior'
    return 'production_behavior'
"""
        result = classify_coupling(code)
        assert result == CouplingClassification.TEST_NAME_BRANCH

    def test_fixture_name_branch_detected(self):
        """Test detection of production code branching on fixture names."""
        code = """
def load_config(source):
    if source == 'fixture_golden_config':
        return get_test_config()
    return get_prod_config()
"""
        result = classify_coupling(code)
        assert result == CouplingClassification.FIXTURE_NAME_BRANCH

    def test_env_flag_branch_detected(self):
        """Test detection of production code branching on TEST_* env vars."""
        code = """
import os
def setup():
    if os.environ.get('TEST_MOCK_DATABASE'):
        return mock_db
    return real_db
"""
        result = classify_coupling(code)
        assert result == CouplingClassification.ENV_FLAG_BRANCH

    def test_ci_marker_only_not_coupling(self):
        """Test that CI marker branching alone is NOT coupling."""
        code = """
import os
def configure():
    if os.environ.get('CI'):
        setup_ci_logging()
    else:
        setup_dev_logging()
"""
        result = classify_coupling(code)
        assert result == CouplingClassification.NO_COUPLING

    def test_ci_marker_with_test_name_is_coupling(self):
        """Test that CI marker context + test name branching IS coupling."""
        code = """
import os
def configure():
    if os.environ.get('CI'):
        pass  # CI setup acceptable
    if mode == 'test_unit_A':
        setup_ci_test_logging()
"""
        result = classify_coupling(code)
        # CI marker alone is no coupling, but separate test name branch is coupling
        assert result == CouplingClassification.TEST_NAME_BRANCH

    def test_data_driven_parser_not_coupling(self):
        """Test that data-driven parser pattern is NOT coupling."""
        code = """
def parse_config(data):
    for entry in data:
        if entry['type'] == 'service':
            parse_service(entry)
        elif entry['type'] == 'database':
            parse_database(entry)
"""
        result = classify_coupling(code)
        assert result == CouplingClassification.DATA_DRIVEN_PARSER

    def test_stable_fixture_mapping_not_coupling(self):
        """Test that stable fixture mapping registry is NOT coupling."""
        code = """
FIXTURE_MAP = {
    'service_a': 'fixtures/service_a.json',
    'service_b': 'fixtures/service_b.json',
}

def get_fixture(name):
    return FIXTURE_MAP.get(name)
"""
        result = classify_coupling(code)
        assert result == CouplingClassification.STABLE_FIXTURE_MAPPING

    def test_no_coupling_clean_code(self):
        """Test that clean production code without test branching returns no coupling."""
        code = """
def process_data(input):
    result = transform(input)
    return validate(result)
"""
        result = classify_coupling(code)
        assert result == CouplingClassification.NO_COUPLING

    def test_golden_fixture_path_branch_detected(self):
        """Test detection of production code branching on golden fixture paths."""
        code = """
def load_test_data(path):
    if path == 'golden/expected_output.json':
        return load_golden()
    return load_regular()
"""
        result = classify_coupling(code)
        assert result == CouplingClassification.GOLDEN_FIXTURE_PATH_BRANCH


# =============================================================================
# Test Oracle Classification
# =============================================================================

class TestOracleClassification:
    """Tests for classify_oracle function."""

    def test_expected_value_oracle_detected(self):
        """Test detection of expected value oracle."""
        evidence = [
            {"record_type": "execution", "payload": {"expected": "success", "actual": "success"}}
        ]
        result = classify_oracle(evidence)
        assert result == OracleClassification.EXPECTED_VALUE

    def test_contract_check_oracle_detected(self):
        """Test detection of contract check oracle."""
        evidence = [
            {"record_type": "contract_evidence", "payload": {"contract": "API契约"}}
        ]
        result = classify_oracle(evidence)
        assert result == OracleClassification.CONTRACT_CHECK

    def test_property_assertion_oracle_detected(self):
        """Test detection of property-based oracle."""
        evidence = [
            {"record_type": "execution", "payload": {"property": "is_positive", "@given": "random_int"}}
        ]
        result = classify_oracle(evidence)
        assert result == OracleClassification.PROPERTY_ASSERTION

    def test_mutation_score_oracle_detected(self):
        """Test detection of mutation testing oracle."""
        evidence = [
            {"record_type": "mutation_evidence", "payload": {"mutation_score": 85}}
        ]
        result = classify_oracle(evidence)
        assert result == OracleClassification.MUTATION_SCORE

    def test_manual_oracle_detected(self):
        """Test detection of manual oracle."""
        evidence = [
            {"record_type": "execution", "payload": {"manual_oracle": True}}
        ]
        result = classify_oracle(evidence)
        assert result == OracleClassification.MANUAL_ORACLE

    def test_no_oracle_detected(self):
        """Test detection of missing oracle."""
        evidence = [
            {"record_type": "coverage", "payload": {"coverage_percentage": 85}}
        ]
        result = classify_oracle(evidence)
        assert result == OracleClassification.NO_ORACLE


# =============================================================================
# Test Coverage Evidence Classification
# =============================================================================

class TestCoverageEvidenceClassification:
    """Tests for classify_coverage_evidence function."""

    def test_executed_tests_with_oracle_good_evidence(self):
        """Test that executed tests with oracle = good evidence."""
        coverage = {"payload": {"executed_tests": ["test_A"], "coverage_percentage": 80}}
        evidence = [{"payload": {"expected": "success"}}]
        result = classify_coverage_evidence(coverage, evidence)
        assert result == CoverageClassification.EXECUTED_TESTS_WITH_ORACLE

    def test_coverage_only_not_meaningful(self):
        """Test that coverage percentage alone is NOT meaningful evidence."""
        coverage = {"payload": {"coverage_percentage": 92, "executed_tests": []}}
        evidence = []
        result = classify_coverage_evidence(coverage, evidence)
        assert result == CoverageClassification.COVERAGE_ONLY

    def test_covered_lines_only_not_meaningful(self):
        """Test that covered lines alone is NOT meaningful evidence."""
        coverage = {"payload": {"covered_lines": ["line1", "line2"], "executed_tests": []}}
        evidence = []
        result = classify_coverage_evidence(coverage, evidence)
        assert result == CoverageClassification.COVERED_LINES_ONLY

    def test_no_coverage_detected(self):
        """Test detection of no coverage."""
        coverage = {"payload": {}}
        evidence = []
        result = classify_coverage_evidence(coverage, evidence)
        assert result == CoverageClassification.NO_COVERAGE


# =============================================================================
# Test Coupling Detection
# =============================================================================

class TestCouplingDetection:
    """Tests for detect_implementation_test_coupling function."""

    def test_test_name_branch_finding_generated(self):
        """Test that test name branch generates finding with hold effect."""
        sources = [
            {
                "file_path": "src/feature.py",
                "code": "if mode == 'test_unit_A': return 'test'",
                "test_ids": ["test_unit_A"],
            }
        ]
        findings = detect_implementation_test_coupling(
            sources,
            fixture_id="test-coupling",
            profile="release",
        )
        assert len(findings) == 1
        assert findings[0].classification == CouplingClassification.TEST_NAME_BRANCH
        assert findings[0].severity == "high"
        assert findings[0].readiness_effect == "hold"
        assert findings[0].manual_review_required

    def test_fixture_name_branch_finding_generated(self):
        """Test that fixture name branch generates finding."""
        sources = [
            {
                "file_path": "src/loader.py",
                "code": "if source == 'fixture_golden': return test_data",
                "fixture_names": ["fixture_golden"],
            }
        ]
        findings = detect_implementation_test_coupling(
            sources,
            fixture_id="fixture-coupling",
            profile="release",
        )
        assert len(findings) == 1
        assert findings[0].classification == CouplingClassification.FIXTURE_NAME_BRANCH
        assert findings[0].readiness_effect == "hold"

    def test_data_driven_parser_no_finding(self):
        """Test that data-driven parser does NOT generate finding."""
        sources = [
            {
                "file_path": "src/parser.py",
                "code": "for entry in data:\n    parse(entry)",
            }
        ]
        findings = detect_implementation_test_coupling(sources)
        assert len(findings) == 0

    def test_stable_fixture_mapping_no_finding(self):
        """Test that stable fixture mapping does NOT generate finding."""
        sources = [
            {
                "file_path": "src/fixtures.py",
                "code": "FIXTURE_MAP = {}\ndef get_fixture(name): return FIXTURE_MAP.get(name)",
            }
        ]
        findings = detect_implementation_test_coupling(sources)
        assert len(findings) == 0


# =============================================================================
# Test Risk Without Oracle Detection
# =============================================================================

class TestRiskWithoutOracleDetection:
    """Tests for detect_risk_without_oracle function."""

    def test_high_risk_without_oracle_hold(self):
        """Test that high/critical risk without oracle generates hold."""
        risk_entries = [
            {"risk_id": "risk-001", "risk_level": "high", "feature_id": "payment"}
        ]
        evidence = [
            {"record_type": "coverage", "payload": {"risk_ref": "risk-001"}}
        ]
        findings = detect_risk_without_oracle(
            risk_entries,
            evidence,
            fixture_id="risk-oracle",
            profile="release",
        )
        assert len(findings) == 1
        assert findings[0].risk_level == "high"
        assert findings[0].oracle_classification == OracleClassification.NO_ORACLE
        assert findings[0].readiness_effect == "hold"
        assert findings[0].manual_review_required

    def test_low_risk_without_oracle_no_finding(self):
        """Test that low risk without oracle does NOT generate finding."""
        risk_entries = [
            {"risk_id": "risk-002", "risk_level": "low", "feature_id": "styling"}
        ]
        evidence = []
        findings = detect_risk_without_oracle(risk_entries, evidence)
        assert len(findings) == 0

    def test_high_risk_with_oracle_no_finding(self):
        """Test that high risk WITH oracle does NOT generate finding."""
        risk_entries = [
            {"risk_id": "risk-003", "risk_level": "high", "feature_id": "auth"}
        ]
        evidence = [
            {"risk_ref": "risk-003", "payload": {"expected": "authenticated"}}
        ]
        findings = detect_risk_without_oracle(risk_entries, evidence)
        assert len(findings) == 0


# =============================================================================
# Test Coverage Without Evidence Detection
# =============================================================================

class TestCoverageWithoutEvidenceDetection:
    """Tests for detect_coverage_without_evidence function."""

    def test_coverage_only_generates_finding(self):
        """Test that coverage only generates finding."""
        coverage = [
            {"coverage_id": "cov-001", "payload": {"coverage_percentage": 85}}
        ]
        evidence = []
        risk_entries = []
        findings = detect_coverage_without_evidence(
            coverage,
            evidence,
            risk_entries,
            fixture_id="coverage-evidence",
        )
        assert len(findings) == 1
        assert findings[0].coverage_classification == CoverageClassification.COVERAGE_ONLY
        assert findings[0].has_oracle == False

    def test_coverage_with_oracle_lower_severity(self):
        """Test that coverage with oracle has lower severity."""
        coverage = [
            {"coverage_id": "cov-002", "payload": {"executed_tests": ["test_A"]}}
        ]
        evidence = [
            {"payload": {"expected": "success"}}
        ]
        risk_entries = []
        findings = detect_coverage_without_evidence(coverage, evidence, risk_entries)
        # With oracle, severity should be low or soft_gap
        assert findings[0].severity in ("low", "medium")

    def test_coverage_as_sole_high_risk_evidence_hold(self):
        """Test that coverage as sole high-risk evidence generates hold."""
        coverage = [
            {
                "coverage_id": "cov-003",
                "payload": {"coverage_percentage": 90, "risk_ref": "risk-high"}
            }
        ]
        evidence = []
        risk_entries = [
            {"risk_id": "risk-high", "risk_level": "high"}
        ]
        findings = detect_coverage_without_evidence(
            coverage,
            evidence,
            risk_entries,
            profile="release",
        )
        # Sole evidence for high risk = hold
        assert findings[0].severity == "high"
        assert findings[0].readiness_effect == "hold"


# =============================================================================
# Test Full Report Generation
# =============================================================================

class TestCouplingIntegrityReport:
    """Tests for build_coupling_integrity_report function."""

    def test_report_structure_complete(self):
        """Test that report has all required fields."""
        report = build_coupling_integrity_report(
            production_sources=[],
            risk_matrix_entries=[],
            evidence_records=[],
            coverage_records=[],
            fixture_id="test-report",
            profile="default",
        )
        assert report["schema_version"] == "HATE/v1"
        assert report["record_type"] == "test_integrity_report"
        assert report["fixture_id"] == "test-report"
        assert "summary" in report
        assert "findings" in report
        assert "test_coupling_findings" in report
        assert "risk_oracle_findings" in report
        assert "coverage_evidence_findings" in report
        assert "risk_debt" in report
        assert "sourceRefs" in report

    def test_report_with_coupling_findings(self):
        """Test that report correctly includes coupling findings."""
        sources = [
            {"file_path": "src/code.py", "code": "if 'test_' in mode: return 'test'", "test_ids": ["test_A"]}
        ]
        report = build_coupling_integrity_report(
            production_sources=sources,
            risk_matrix_entries=[],
            evidence_records=[],
            coverage_records=[],
            fixture_id="coupling-report",
            profile="release",
        )
        assert len(report["test_coupling_findings"]) == 1
        assert report["summary"]["overall_status"] == "hold"

    def test_report_aggregates_source_refs(self):
        """Test that report aggregates source refs from all findings."""
        sources = [
            {"file_path": "src/a.py", "code": "if 'test_' in mode: return 'test'", "source_ref": "prod:src/a.py"}
        ]
        risks = [
            {"risk_id": "risk-1", "risk_level": "high", "source_refs": ["risk:risk-1"]}
        ]
        coverage = [
            {"coverage_id": "cov-1", "payload": {}, "source_refs": ["cov:cov-1"]}
        ]
        report = build_coupling_integrity_report(
            production_sources=sources,
            risk_matrix_entries=risks,
            evidence_records=[],
            coverage_records=coverage,
            fixture_id="refs-report",
        )
        assert len(report["sourceRefs"]) >= 2


# =============================================================================
# Test Manual Review Classification
# =============================================================================

class TestManualReviewClassification:
    """Tests for manual review classification and request generation."""

    def test_fixture_coupling_requires_review(self):
        """Test that fixture coupling requires manual review."""
        finding = {
            "finding_id": "finding-001",
            "evidence_class": "implementation_test_coupling",
            "classification": "fixture_name_branch",
            "severity": "high",
        }
        classification = classify_manual_review_requirement(finding, [], "2026-01-01T00:00:00Z")
        assert classification == ManualReviewClassification.FIXTURE_NAME_COUPLING

    def test_valid_human_record_no_request(self):
        """Test that valid human record does NOT generate request."""
        finding = {
            "finding_id": "finding-002",
            "evidence_class": "mock_abuse_detected",
            "severity": "medium",
        }
        records = [
            {
                "evidence_ref": "finding-002",
                "expiry": "2027-01-01T00:00:00Z",
                "owner": "team-A",
            }
        ]
        classification = classify_manual_review_requirement(
            finding, records, "2026-01-01T00:00:00Z"
        )
        assert classification == ManualReviewClassification.VALID_MANUAL_REVIEW

        request = generate_manual_review_request(finding, classification)
        assert request is None

    def test_expired_human_record_renewal(self):
        """Test that expired human record generates renewal request."""
        finding = {
            "finding_id": "finding-003",
            "evidence_class": "risk_without_oracle",
            "severity": "high",
        }
        records = [
            {
                "evidence_ref": "finding-003",
                "expiry": "2025-01-01T00:00:00Z",
                "owner": "team-B",
            }
        ]
        classification = classify_manual_review_requirement(
            finding, records, "2026-01-01T00:00:00Z"
        )
        assert classification == ManualReviewClassification.EXPIRED_HUMAN_RECORD

        request = generate_manual_review_request(finding, classification)
        assert request is not None
        assert request["required_decision"] in REQUIRED_DECISION_TYPES

    def test_missing_oracle_requires_review(self):
        """Test that missing oracle requires manual review."""
        finding = {
            "finding_id": "finding-004",
            "evidence_class": "risk_without_oracle",
            "severity": "critical",
        }
        classification = classify_manual_review_requirement(finding, [], "2026-01-01T00:00:00Z")
        assert classification == ManualReviewClassification.MISSING_ORACLE

        request = generate_manual_review_request(finding, classification)
        assert request["blocking"] == True


# =============================================================================
# Test Manual Review Processing
# =============================================================================

class TestManualReviewProcessing:
    """Tests for process_manual_review_requests function."""

    def test_processes_multiple_findings(self):
        """Test that multiple findings are processed."""
        findings = [
            {"finding_id": "f1", "evidence_class": "mock_abuse_detected", "severity": "medium"},
            {"finding_id": "f2", "evidence_class": "risk_without_oracle", "severity": "high"},
        ]
        report = process_manual_review_requests(findings, [], fixture_id="multi-review")
        assert report["summary"]["finding_count"] == 2
        assert report["summary"]["request_count"] >= 1

    def test_valid_records_counted(self):
        """Test that valid human records are counted."""
        findings = [
            {"finding_id": "f-valid", "evidence_class": "mock_abuse_detected", "severity": "low"}
        ]
        records = [
            {"evidence_ref": "f-valid", "expiry": "2027-01-01T00:00:00Z"}
        ]
        report = process_manual_review_requests(
            findings, records, fixture_id="valid-review", now="2026-01-01T00:00:00Z"
        )
        assert report["summary"]["valid_count"] >= 1


# =============================================================================
# Test Human Record Expiry Check
# =============================================================================

class TestHumanRecordExpiryCheck:
    """Tests for check_human_record_expiry function."""

    def test_expired_records_detected(self):
        """Test that expired records are detected."""
        records = [
            {"record_id": "r1", "expiry": "2025-01-01T00:00:00Z"},
            {"record_id": "r2", "expiry": "2027-01-01T00:00:00Z"},
        ]
        report = check_human_record_expiry(records, now="2026-01-01T00:00:00Z")
        assert report["summary"]["expired_count"] == 1
        assert len(report["expired_records"]) == 1

    def test_expiring_soon_detected(self):
        """Test that expiring within 30 days are detected."""
        records = [
            {"record_id": "r-expiring", "expiry": "2026-01-20T00:00:00Z"}
        ]
        report = check_human_record_expiry(records, now="2026-01-01T00:00:00Z")
        assert report["summary"]["expiring_soon_count"] >= 1

    def test_renewal_requests_generated(self):
        """Test that renewal requests are generated for expired."""
        records = [
            {"record_id": "r-old", "expiry": "2025-01-01T00:00:00Z", "owner": "team-X"}
        ]
        report = check_human_record_expiry(records, now="2026-01-01T00:00:00Z")
        assert len(report["renewal_requests"]) == 1
        assert report["renewal_requests"][0]["required_decision"] == "extend_expiry_or_close"


# =============================================================================
# Test Detector ID Constants
# =============================================================================

class TestDetectorIDs:
    """Tests for detector ID constants."""

    def test_coupling_detector_id_defined(self):
        """Test that coupling detector ID is defined."""
        assert DETECTOR_ID_COUPLING == "hate.pg004c.coupling_detector"

    def test_required_decision_types_defined(self):
        """Test that required decision types include expected values."""
        assert "approve_or_reject" in REQUIRED_DECISION_TYPES
        assert "verify_coupling_or_remove_branch" in REQUIRED_DECISION_TYPES
        assert "add_oracle_or_accept_risk" in REQUIRED_DECISION_TYPES


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests combining multiple detection paths."""

    def test_full_workflow_coupling_to_review(self):
        """Test full workflow from coupling detection to review request."""
        sources = [
            {"file_path": "src/coupled.py", "code": "if 'test_' in name: return 'mock'", "test_ids": ["test_A"]}
        ]
        report = build_coupling_integrity_report(
            production_sources=sources,
            risk_matrix_entries=[],
            evidence_records=[],
            coverage_records=[],
            fixture_id="full-workflow",
            profile="release",
        )

        # Process for manual review
        review_report = process_manual_review_requests(
            report["findings"],
            [],
            fixture_id="full-workflow-review",
        )

        assert review_report["summary"]["request_count"] >= 1
        assert review_report["summary"]["overall_status"] in ("blocked", "pending")

    def test_combined_findings_all_types(self):
        """Test combined findings from coupling, risk, coverage."""
        sources = [
            {"file_path": "src/c.py", "code": "if 'test_' in mode: return 'test'", "test_ids": ["t"]}
        ]
        risks = [
            {"risk_id": "r-high", "risk_level": "high", "source_refs": ["risk:r-high"]}
        ]
        coverage = [
            {"coverage_id": "cov-1", "payload": {"coverage_percentage": 85}}
        ]

        report = build_coupling_integrity_report(
            production_sources=sources,
            risk_matrix_entries=risks,
            evidence_records=[],
            coverage_records=coverage,
            fixture_id="combined-findings",
            profile="release",
        )

        # Should have findings from all three detection types
        assert len(report["test_coupling_findings"]) >= 1
        assert len(report["risk_oracle_findings"]) >= 1
        assert len(report["coverage_evidence_findings"]) >= 1

        # Overall status should be hold (worst effect)
        assert report["summary"]["overall_status"] == "hold"


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_sources_no_findings(self):
        """Test that empty sources produce no findings."""
        findings = detect_implementation_test_coupling([])
        assert len(findings) == 0

    def test_empty_risks_no_findings(self):
        """Test that empty risks produce no findings."""
        findings = detect_risk_without_oracle([], [])
        assert len(findings) == 0

    def test_empty_coverage_no_findings(self):
        """Test that empty coverage produces no findings."""
        findings = detect_coverage_without_evidence([], [], [])
        assert len(findings) == 0

    def test_invalid_expiry_date_handled(self):
        """Test that invalid expiry date is handled gracefully."""
        records = [
            {"record_id": "r-invalid", "expiry": "invalid-date"}
        ]
        report = check_human_record_expiry(records, now="2026-01-01T00:00:00Z")
        # Should not crash, mark as valid with invalid_date status
        assert report["summary"]["total_records"] == 1

    def test_confidence_range_valid(self):
        """Test that confidence is always in valid range."""
        sources = [
            {"file_path": "src/c.py", "code": "if 'test_' in mode: return 'test'", "test_ids": ["t"]}
        ]
        findings = detect_implementation_test_coupling(sources)
        for f in findings:
            assert 0.0 <= f.confidence <= 1.0
