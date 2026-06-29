"""Fixture and schema tests for HATE-PG-004C coupling detector."""

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
# Canonical Fixture Tests
# =============================================================================

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "test-integrity" / "coupling"


class TestCanonicalFixtures:
    """Tests for canonical fixture files in new directory layout."""

    def test_fixture_data_driven_parser(self):
        """Test data-driven-parser fixture exists and is valid."""
        fixture_path = FIXTURE_DIR / "data-driven-parser" / "fixture.json"
        assert fixture_path.exists(), f"Missing fixture: {fixture_path}"
        fixture = json.loads(fixture_path.read_text())
        assert fixture["fixture_id"] == "data-driven-parser"
        assert fixture["expected_status"] == "pass"
        assert len(fixture["expected_findings"]) == 0

    def test_fixture_fixture_renamed_stable(self):
        """Test fixture-renamed-stable fixture exists and is valid."""
        fixture_path = FIXTURE_DIR / "fixture-renamed-stable" / "fixture.json"
        assert fixture_path.exists(), f"Missing fixture: {fixture_path}"
        fixture = json.loads(fixture_path.read_text())
        assert fixture["fixture_id"] == "fixture-renamed-stable"
        assert fixture["expected_status"] == "pass"

    def test_fixture_test_name_branch(self):
        """Test test-name-branch fixture exists and is valid."""
        fixture_path = FIXTURE_DIR / "test-name-branch" / "fixture.json"
        assert fixture_path.exists(), f"Missing fixture: {fixture_path}"
        fixture = json.loads(fixture_path.read_text())
        assert fixture["fixture_id"] == "test-name-branch"
        assert fixture["expected_status"] == "hold"
        assert len(fixture["expected_findings"]) >= 1
        assert fixture["expected_findings"][0]["classification"] == "test_name_branch"

    def test_fixture_fixture_name_branch(self):
        """Test fixture-name-branch fixture exists and is valid."""
        fixture_path = FIXTURE_DIR / "fixture-name-branch" / "fixture.json"
        assert fixture_path.exists(), f"Missing fixture: {fixture_path}"
        fixture = json.loads(fixture_path.read_text())
        assert fixture["fixture_id"] == "fixture-name-branch"
        assert fixture["expected_status"] == "hold"
        assert fixture["expected_findings"][0]["classification"] == "fixture_name_branch"

    def test_fixture_risk_without_oracle(self):
        """Test risk-without-oracle fixture exists and is valid."""
        fixture_path = FIXTURE_DIR / "risk-without-oracle" / "fixture.json"
        assert fixture_path.exists(), f"Missing fixture: {fixture_path}"
        fixture = json.loads(fixture_path.read_text())
        assert fixture["fixture_id"] == "risk-without-oracle"
        assert fixture["expected_status"] == "hold"
        assert fixture["expected_findings"][0]["risk_level"] == "critical"

    def test_fixture_coverage_without_evidence(self):
        """Test coverage-without-evidence fixture exists and is valid."""
        fixture_path = FIXTURE_DIR / "coverage-without-evidence" / "fixture.json"
        assert fixture_path.exists(), f"Missing fixture: {fixture_path}"
        fixture = json.loads(fixture_path.read_text())
        assert fixture["fixture_id"] == "coverage-without-evidence"
        assert fixture["expected_status"] == "soft_gap"
        assert fixture["expected_findings"][0]["evidence_class"] == "coverage_without_evidence"

    def test_fixture_coverage_with_executed_tests(self):
        """Test coverage-with-executed-tests fixture exists and is valid."""
        fixture_path = FIXTURE_DIR / "coverage-with-executed-tests" / "fixture.json"
        assert fixture_path.exists(), f"Missing fixture: {fixture_path}"
        fixture = json.loads(fixture_path.read_text())
        assert fixture["fixture_id"] == "coverage-with-executed-tests"
        assert fixture["expected_status"] == "pass"
        assert len(fixture["expected_findings"]) == 0

    def test_fixture_manual_review_owned(self):
        """Test manual-review-owned fixture exists and is valid."""
        fixture_path = FIXTURE_DIR / "manual-review-owned" / "fixture.json"
        assert fixture_path.exists(), f"Missing fixture: {fixture_path}"
        fixture = json.loads(fixture_path.read_text())
        assert fixture["fixture_id"] == "manual-review-owned"
        assert fixture["expected_status"] == "pass"
        assert len(fixture["human_records"]) >= 1

    def test_fixture_manual_review_without_human_record(self):
        """Test manual-review-without-human-record fixture exists and is valid."""
        fixture_path = FIXTURE_DIR / "manual-review-without-human-record" / "fixture.json"
        assert fixture_path.exists(), f"Missing fixture: {fixture_path}"
        fixture = json.loads(fixture_path.read_text())
        assert fixture["fixture_id"] == "manual-review-without-human-record"
        assert fixture["expected_status"] == "hold"
        assert len(fixture["human_records"]) == 0

    def test_fixture_manual_review_expired(self):
        """Test manual-review-expired fixture exists and is valid."""
        fixture_path = FIXTURE_DIR / "manual-review-expired" / "fixture.json"
        assert fixture_path.exists(), f"Missing fixture: {fixture_path}"
        fixture = json.loads(fixture_path.read_text())
        assert fixture["fixture_id"] == "manual-review-expired"
        assert fixture["expected_status"] == "hold"
        assert len(fixture["human_records"]) >= 1


# =============================================================================
# Schema Validation Tests
# =============================================================================

SCHEMA_DIR = Path(__file__).parent.parent / "schemas" / "HATE" / "v1"


def assert_schema_required_shape(schema: dict, document: dict) -> None:
    """Validate required fields/enums without optional third-party dependencies."""
    assert set(schema["required"]) <= set(document)
    summary_schema = schema["properties"]["summary"]
    assert set(summary_schema["required"]) <= set(document["summary"])
    assert document["summary"]["overall_status"] in summary_schema["properties"]["overall_status"]["enum"]

    request_schema = schema["properties"]["requests"]["items"]
    for request in document["requests"]:
        assert set(request_schema["required"]) <= set(request)
        assert request["status"] in request_schema["properties"]["status"]["enum"]
        assert request["required_decision"] in request_schema["properties"]["required_decision"]["enum"]

    finding_schema = schema["properties"]["findings"]["items"]
    for finding in document["findings"]:
        assert set(finding_schema["required"]) <= set(finding)


class TestManualReviewSchemaValidation:
    """Tests for manual review output schema validation."""

    def test_manual_review_request_bundle_schema(self):
        """Test that process_manual_review_requests output matches schema."""
        schema_path = SCHEMA_DIR / "manual-review-request.schema.json"
        assert schema_path.exists(), f"Missing schema: {schema_path}"
        schema = json.loads(schema_path.read_text())

        findings = [
            {"finding_id": "f1", "evidence_class": "risk_without_oracle", "severity": "high", "sourceRefs": ["risk:1"]}
        ]
        result = process_manual_review_requests(findings, [], fixture_id="schema-test")

        assert_schema_required_shape(schema, result)

    def test_schema_record_type_bundle(self):
        """Test that record_type is manual_review_request_bundle."""
        schema_path = SCHEMA_DIR / "manual-review-request.schema.json"
        schema = json.loads(schema_path.read_text())
        assert schema["properties"]["record_type"]["const"] == "manual_review_request_bundle"

        findings = []
        result = process_manual_review_requests(findings, [], fixture_id="type-test")
        assert result["record_type"] == "manual_review_request_bundle"

    def test_schema_summary_fields_required(self):
        """Test that summary has all required fields."""
        schema_path = SCHEMA_DIR / "manual-review-request.schema.json"
        schema = json.loads(schema_path.read_text())
        required_summary = schema["properties"]["summary"]["required"]
        expected = ["overall_status", "request_count", "pending_count", "hard_dq_count", "missing_owner_count", "expired_count"]
        for field in expected:
            assert field in required_summary, f"Missing required summary field: {field}"

        findings = []
        result = process_manual_review_requests(findings, [], fixture_id="summary-test")
        for field in expected:
            assert field in result["summary"], f"Missing summary field in output: {field}"

    def test_schema_findings_format(self):
        """Test that findings have code, severity, message, sourceRef."""
        schema_path = SCHEMA_DIR / "manual-review-request.schema.json"
        schema = json.loads(schema_path.read_text())
        required_finding = schema["properties"]["findings"]["items"]["required"]
        assert "code" in required_finding
        assert "severity" in required_finding
        assert "message" in required_finding
        assert "sourceRef" in required_finding

        findings = [
            {"finding_id": "f-schema", "evidence_class": "test_class", "severity": "medium", "reason": "test reason", "sourceRefs": ["ref:1"]}
        ]
        result = process_manual_review_requests(findings, [], fixture_id="findings-format-test")
        for f in result["findings"]:
            assert "code" in f
            assert "severity" in f
            assert "message" in f
            assert "sourceRef" in f

    def test_schema_overall_status_enum(self):
        """Test that overall_status uses correct enum values."""
        schema_path = SCHEMA_DIR / "manual-review-request.schema.json"
        schema = json.loads(schema_path.read_text())
        allowed = schema["properties"]["summary"]["properties"]["overall_status"]["enum"]
        assert allowed == ["ready", "pending", "blocked"]

        # Test blocked status
        blocked_findings = [
            {"finding_id": "f-block", "evidence_class": "risk_without_oracle", "severity": "critical", "sourceRefs": ["r:1"]}
        ]
        result = process_manual_review_requests(blocked_findings, [], fixture_id="blocked-test")
        assert result["summary"]["overall_status"] in allowed

        # Test ready status (no findings)
        result_ready = process_manual_review_requests([], [], fixture_id="ready-test")
        assert result_ready["summary"]["overall_status"] == "ready"
