"""Tests for test integrity skip/focus/todo detector - HATE-PG-004A."""

from __future__ import annotations

import json
import pytest
from pathlib import Path

from hate.test_integrity import (
    IntegrityFinding,
    IntegritySignalType,
    detect_test_integrity_signals,
    build_test_integrity_report,
)
from hate.test_integrity.models import (
    IntegrityRiskDebt,
    AntiEvasionMatch,
    SIGNAL_SEVERITY_MATRIX,
    DETECTOR_ID_SKIP_FOCUS,
)


# Fixture paths - task-packet structure
FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "test-integrity" / "skip-focus"

# Required fixture names per task packet
REQUIRED_FIXTURES = [
    "clean-suite",
    "known-skip-with-owner",
    "xfail-with-issue-ref",
    "todo-non-release-profile",
    "only-focused-leak",
    "skip-without-reason",
    "xfail-without-expiry",
    "todo-in-release-profile",
    "skip-in-critical-risk-area",
]

# Canonical finding fields per task packet
CANONICAL_FINDING_FIELDS = [
    "finding_id",
    "detector_id",
    "severity",
    "profile",
    "affected_test_id",
    "marker_kind",
    "reason",
    "owner",
    "expiry",
    "sourceRef",
    "readiness_effect",
    "suggested_manual_review_action",
]


class TestFixturePathsExist:
    """Tests for required fixture paths existence."""

    @pytest.mark.parametrize("fixture_name", REQUIRED_FIXTURES)
    def test_fixture_directory_exists(self, fixture_name):
        """Each required fixture directory must exist."""
        fixture_path = FIXTURE_DIR / fixture_name
        assert fixture_path.exists(), f"Fixture directory missing: {fixture_path}"

    @pytest.mark.parametrize("fixture_name", REQUIRED_FIXTURES)
    def test_fixture_json_exists(self, fixture_name):
        """Each required fixture must have fixture.json."""
        fixture_path = FIXTURE_DIR / fixture_name / "fixture.json"
        assert fixture_path.exists(), f"fixture.json missing: {fixture_path}"

    @pytest.mark.parametrize("fixture_name", REQUIRED_FIXTURES)
    def test_fixture_json_valid(self, fixture_name):
        """Each fixture.json must be valid JSON with required fields."""
        fixture_path = FIXTURE_DIR / fixture_name / "fixture.json"
        fixture = json.loads(fixture_path.read_text())
        assert "test_records" in fixture
        assert "profile" in fixture
        assert "expected_summary" in fixture


class TestCanonicalFindingFields:
    """Tests for canonical finding fields per task packet."""

    def test_integrity_finding_has_all_canonical_fields(self):
        """IntegrityFinding must have all canonical fields."""
        finding = IntegrityFinding(
            finding_id="test.skip.test_example",
            detector_id=DETECTOR_ID_SKIP_FOCUS,
            severity="medium",
            profile="release",
            affected_test_id="test_example",
            marker_kind="skip",
            reason="Test has skip marker without reason",
            owner=None,
            expiry=None,
            sourceRef="tests/test.py",
            readiness_effect="hold",
            suggested_manual_review_action="Add skip reason and owner",
        )

        # Verify all canonical fields are accessible
        assert finding.finding_id == "test.skip.test_example"
        assert finding.detector_id == DETECTOR_ID_SKIP_FOCUS
        assert finding.severity == "medium"
        assert finding.profile == "release"
        assert finding.affected_test_id == "test_example"
        assert finding.marker_kind == "skip"
        assert finding.reason == "Test has skip marker without reason"
        assert finding.owner is None
        assert finding.expiry is None
        assert finding.sourceRef == "tests/test.py"
        assert finding.readiness_effect == "hold"
        assert finding.suggested_manual_review_action == "Add skip reason and owner"

    def test_integrity_finding_as_dict_has_canonical_fields(self):
        """IntegrityFinding.as_dict() must include all canonical fields."""
        finding = IntegrityFinding(
            finding_id="test.skip.test_example",
            detector_id=DETECTOR_ID_SKIP_FOCUS,
            severity="medium",
            profile="release",
            affected_test_id="test_example",
            marker_kind="skip",
            reason="Test has skip marker without reason",
            owner=None,
            expiry=None,
            sourceRef="tests/test.py",
            readiness_effect="hold",
            suggested_manual_review_action="Add skip reason and owner",
        )

        d = finding.as_dict()

        # All canonical fields must be present
        for field in CANONICAL_FINDING_FIELDS:
            assert field in d, f"Missing canonical field: {field}"

        # Compatibility aliases must be present
        assert "signal_id" in d
        assert "affected_refs" in d
        assert "product_effect" in d
        assert "recommended_action" in d
        assert "sourceRefs" in d

    def test_finding_from_detector_has_canonical_fields(self):
        """Findings generated by detector must have all canonical fields."""
        fixture_path = FIXTURE_DIR / "skip-without-reason" / "fixture.json"
        fixture = json.loads(fixture_path.read_text())

        findings, _ = detect_test_integrity_signals(
            fixture["test_records"],
            profile=fixture["profile"],
        )

        assert len(findings) >= 1
        finding_dict = findings[0].as_dict()

        for field in CANONICAL_FINDING_FIELDS:
            assert field in finding_dict, f"Missing canonical field in finding: {field}"

    def test_detector_id_is_correct(self):
        """All findings must have correct detector_id."""
        fixture_path = FIXTURE_DIR / "skip-without-reason" / "fixture.json"
        fixture = json.loads(fixture_path.read_text())

        findings, _ = detect_test_integrity_signals(
            fixture["test_records"],
            profile=fixture["profile"],
        )

        for finding in findings:
            assert finding.detector_id == DETECTOR_ID_SKIP_FOCUS


class TestDetectTestIntegritySignals:
    """Tests for detect_test_integrity_signals function."""

    def test_clean_suite_no_findings(self):
        """Positive fixture: clean-suite should have no findings."""
        fixture_path = FIXTURE_DIR / "clean-suite" / "fixture.json"
        fixture = json.loads(fixture_path.read_text())

        findings, anti_evasion = detect_test_integrity_signals(
            fixture["test_records"],
            profile=fixture["profile"],
        )

        assert len(findings) == 0
        assert len(anti_evasion) == 0

    def test_known_skip_with_owner_soft_gap(self):
        """Positive fixture: skip with owner/reason is soft_gap in default profile."""
        fixture_path = FIXTURE_DIR / "known-skip-with-owner" / "fixture.json"
        fixture = json.loads(fixture_path.read_text())

        findings, anti_evasion = detect_test_integrity_signals(
            fixture["test_records"],
            profile=fixture["profile"],
        )

        assert len(findings) == 1
        assert findings[0].marker_kind == "skip"
        assert findings[0].readiness_effect == "soft_gap"
        assert findings[0].severity == "low"

    def test_xfail_with_issue_ref_soft_gap(self):
        """Positive fixture: xfail with issue ref and expiry is soft_gap."""
        fixture_path = FIXTURE_DIR / "xfail-with-issue-ref" / "fixture.json"
        fixture = json.loads(fixture_path.read_text())

        findings, anti_evasion = detect_test_integrity_signals(
            fixture["test_records"],
            profile=fixture["profile"],
        )

        assert len(findings) == 1
        assert findings[0].marker_kind == "xfail"
        assert findings[0].readiness_effect == "soft_gap"

    def test_todo_non_release_soft_gap(self):
        """Positive fixture: todo in non-release profile is soft_gap."""
        fixture_path = FIXTURE_DIR / "todo-non-release-profile" / "fixture.json"
        fixture = json.loads(fixture_path.read_text())

        findings, anti_evasion = detect_test_integrity_signals(
            fixture["test_records"],
            profile=fixture["profile"],
        )

        assert len(findings) == 1
        assert findings[0].marker_kind == "todo"
        assert findings[0].readiness_effect == "soft_gap"

    def test_only_focused_leak_blocked_in_release(self):
        """Negative fixture: only marker is blocked in release profile."""
        fixture_path = FIXTURE_DIR / "only-focused-leak" / "fixture.json"
        fixture = json.loads(fixture_path.read_text())

        findings, anti_evasion = detect_test_integrity_signals(
            fixture["test_records"],
            profile=fixture["profile"],
        )

        assert len(findings) == 1
        assert findings[0].marker_kind == "only"
        assert findings[0].readiness_effect == "blocked"
        assert findings[0].severity == "high"

    def test_skip_without_reason_hold_in_release(self):
        """Negative fixture: skip without reason is hold in release."""
        fixture_path = FIXTURE_DIR / "skip-without-reason" / "fixture.json"
        fixture = json.loads(fixture_path.read_text())

        findings, anti_evasion = detect_test_integrity_signals(
            fixture["test_records"],
            profile=fixture["profile"],
        )

        assert len(findings) == 1
        assert findings[0].marker_kind == "skip"
        assert findings[0].readiness_effect == "hold"
        assert findings[0].severity == "medium"
        assert "without reason" in findings[0].reason

    def test_xfail_without_expiry_hold_in_release(self):
        """Negative fixture: xfail without expiry is hold in release."""
        fixture_path = FIXTURE_DIR / "xfail-without-expiry" / "fixture.json"
        fixture = json.loads(fixture_path.read_text())

        findings, anti_evasion = detect_test_integrity_signals(
            fixture["test_records"],
            profile=fixture["profile"],
        )

        assert len(findings) == 1
        assert findings[0].marker_kind == "xfail"
        assert findings[0].readiness_effect == "hold"
        assert findings[0].severity == "high"
        assert "without expiry" in findings[0].reason

    def test_todo_in_release_blocked(self):
        """Negative fixture: todo in release profile is blocked."""
        fixture_path = FIXTURE_DIR / "todo-in-release-profile" / "fixture.json"
        fixture = json.loads(fixture_path.read_text())

        findings, anti_evasion = detect_test_integrity_signals(
            fixture["test_records"],
            profile=fixture["profile"],
        )

        assert len(findings) == 1
        assert findings[0].marker_kind == "todo"
        assert findings[0].readiness_effect == "blocked"
        assert findings[0].severity == "high"

    def test_skip_in_critical_risk_area_blocked(self):
        """Negative fixture: skip in critical risk area is blocked."""
        fixture_path = FIXTURE_DIR / "skip-in-critical-risk-area" / "fixture.json"
        fixture = json.loads(fixture_path.read_text())

        findings, anti_evasion = detect_test_integrity_signals(
            fixture["test_records"],
            profile=fixture["profile"],
        )

        assert len(findings) == 1
        assert findings[0].marker_kind == "skip"
        assert findings[0].readiness_effect == "blocked"
        assert findings[0].severity == "critical"


class TestAntiEvasionPatterns:
    """Tests for anti-evasion pattern detection."""

    def test_jest_only_detected_in_message(self):
        """Anti-evasion: detect jest .only in message field."""
        test_records = [{
            "canonical_test_id": "test_hidden_focus",
            "framework": "jest",
            "status": "passed",
            "message": "Running describe.only for debugging",
            "sourceRefs": ["tests/test.js"],
        }]

        findings, anti_evasion = detect_test_integrity_signals(
            test_records,
            profile="release",
        )

        assert len(anti_evasion) >= 1
        assert any(m.pattern == "jest_only" for m in anti_evasion)

        # Should also generate a finding
        only_findings = [f for f in findings if f.marker_kind == "only"]
        assert len(only_findings) >= 1

    def test_jest_fit_focus_detected(self):
        """Anti-evasion: detect jest fit() focus pattern."""
        test_records = [{
            "canonical_test_id": "test_fit",
            "framework": "jest",
            "status": "passed",
            "message": "fit('should work', () => {})",
            "sourceRefs": ["tests/test.js"],
        }]

        findings, anti_evasion = detect_test_integrity_signals(
            test_records,
            profile="release",
        )

        assert len(anti_evasion) >= 1
        assert any(m.pattern == "jest_fit_focus" for m in anti_evasion)

    def test_pytest_mark_skip_detected(self):
        """Anti-evasion: detect pytest @pytest.mark.skip in message."""
        test_records = [{
            "canonical_test_id": "test_pytest_skip",
            "framework": "pytest",
            "status": "passed",
            "message": "@pytest.mark.skip(reason='temp')",
            "sourceRefs": ["tests/test.py"],
        }]

        findings, anti_evasion = detect_test_integrity_signals(
            test_records,
            profile="default",
        )

        assert len(anti_evasion) >= 1
        assert any(m.pattern == "pytest_mark_skip" for m in anti_evasion)

    def test_vitest_todo_detected(self):
        """Anti-evasion: detect vitest .todo pattern."""
        test_records = [{
            "canonical_test_id": "test_vitest_todo",
            "framework": "vitest",
            "status": "passed",
            "message": "test.todo('implement later')",
            "sourceRefs": ["tests/test.ts"],
        }]

        findings, anti_evasion = detect_test_integrity_signals(
            test_records,
            profile="release",
        )

        assert len(anti_evasion) >= 1
        assert any(m.pattern == "vitest_todo" for m in anti_evasion)


class TestBuildTestIntegrityReport:
    """Tests for build_test_integrity_report function."""

    def test_report_structure(self):
        """Test that report has required structure."""
        test_records = [{
            "canonical_test_id": "test_example",
            "framework": "pytest",
            "status": "skipped",
            "skip": True,
            "sourceRefs": ["tests/test.py"],
        }]

        report = build_test_integrity_report(
            test_records,
            profile="default",
            fixture_id="test-report",
        )

        assert report["schema_version"] == "HATE/v1"
        assert report["record_type"] == "test_integrity_report"
        assert report["fixture_id"] == "test-report"
        assert report["profile"] == "default"
        assert "summary" in report
        assert "findings" in report
        assert "risk_debt" in report
        assert "anti_evasion" in report
        assert "sourceRefs" in report

    def test_report_summary_overall_status_blocked(self):
        """Test summary overall_status calculation for blocked."""
        fixture_path = FIXTURE_DIR / "only-focused-leak" / "fixture.json"
        fixture = json.loads(fixture_path.read_text())

        report = build_test_integrity_report(
            fixture["test_records"],
            profile=fixture["profile"],
        )

        assert report["summary"]["overall_status"] == "blocked"
        assert report["summary"]["blocked_count"] == 1

    def test_report_summary_overall_status_hold(self):
        """Test summary overall_status calculation for hold."""
        fixture_path = FIXTURE_DIR / "skip-without-reason" / "fixture.json"
        fixture = json.loads(fixture_path.read_text())

        report = build_test_integrity_report(
            fixture["test_records"],
            profile=fixture["profile"],
        )

        assert report["summary"]["overall_status"] == "hold"
        assert report["summary"]["hold_count"] == 1

    def test_report_summary_overall_status_soft_gap(self):
        """Test summary overall_status calculation for soft_gap."""
        fixture_path = FIXTURE_DIR / "known-skip-with-owner" / "fixture.json"
        fixture = json.loads(fixture_path.read_text())

        report = build_test_integrity_report(
            fixture["test_records"],
            profile=fixture["profile"],
        )

        assert report["summary"]["overall_status"] == "soft_gap"
        assert report["summary"]["soft_gap_count"] == 1

    def test_report_summary_overall_status_pass(self):
        """Test summary overall_status calculation for pass."""
        fixture_path = FIXTURE_DIR / "clean-suite" / "fixture.json"
        fixture = json.loads(fixture_path.read_text())

        report = build_test_integrity_report(
            fixture["test_records"],
            profile=fixture["profile"],
        )

        assert report["summary"]["overall_status"] == "pass"
        assert report["summary"]["finding_count"] == 0

    def test_report_source_refs_aggregated(self):
        """Test that sourceRefs are aggregated from all findings."""
        test_records = [
            {
                "canonical_test_id": "test_one",
                "framework": "pytest",
                "status": "skipped",
                "skip": True,
                "sourceRefs": ["tests/one.py"],
            },
            {
                "canonical_test_id": "test_two",
                "framework": "pytest",
                "status": "skipped",
                "skip": True,
                "sourceRefs": ["tests/two.py"],
            },
        ]

        report = build_test_integrity_report(
            test_records,
            profile="default",
        )

        assert "tests/one.py" in report["sourceRefs"]
        assert "tests/two.py" in report["sourceRefs"]

    def test_risk_debt_generated_for_blocked(self):
        """Test that risk debt is generated for blocked findings."""
        fixture_path = FIXTURE_DIR / "only-focused-leak" / "fixture.json"
        fixture = json.loads(fixture_path.read_text())

        report = build_test_integrity_report(
            fixture["test_records"],
            profile=fixture["profile"],
        )

        assert len(report["risk_debt"]) >= 1
        debt = report["risk_debt"][0]
        assert debt["debt_type"] == "integrity_only"
        assert debt["severity"] == "high"
        assert debt["blocking_profile"] == ["release", "product"]

    def test_risk_debt_generated_for_hold(self):
        """Test that risk debt is generated for hold findings."""
        fixture_path = FIXTURE_DIR / "skip-without-reason" / "fixture.json"
        fixture = json.loads(fixture_path.read_text())

        report = build_test_integrity_report(
            fixture["test_records"],
            profile=fixture["profile"],
        )

        assert len(report["risk_debt"]) >= 1
        debt = report["risk_debt"][0]
        assert debt["debt_type"] == "integrity_skip"
        assert debt["blocking_profile"] == ["release"]

    def test_risk_debt_visible_for_accepted_skip(self):
        """Accepted skip with owner still generates visible risk_debt (not hidden pass)."""
        fixture_path = FIXTURE_DIR / "known-skip-with-owner" / "fixture.json"
        fixture = json.loads(fixture_path.read_text())

        report = build_test_integrity_report(
            fixture["test_records"],
            profile=fixture["profile"],
        )

        # Accepted skip/xfail/todo must emit visible risk_debt, not hidden clean pass
        assert len(report["risk_debt"]) >= 1
        debt = report["risk_debt"][0]
        assert debt["debt_type"] == "integrity_skip"
        assert debt["status"] == "accepted"  # Has owner, so accepted status
        assert debt["blocking_profile"] == []  # Not blocking any profile (soft_gap)

    def test_by_signal_type_count(self):
        """Test that by_signal_type counts are correct."""
        test_records = [
            {
                "canonical_test_id": "test_skip",
                "framework": "pytest",
                "status": "skipped",
                "skip": True,
                "sourceRefs": ["tests/skip.py"],
            },
            {
                "canonical_test_id": "test_only",
                "framework": "jest",
                "status": "passed",
                "only": True,
                "sourceRefs": ["tests/only.js"],
            },
        ]

        report = build_test_integrity_report(
            test_records,
            profile="release",
        )

        assert report["summary"]["by_signal_type"]["skip"] == 1
        assert report["summary"]["by_signal_type"]["only"] == 1
        assert report["summary"]["by_signal_type"]["xfail"] == 0
        assert report["summary"]["by_signal_type"]["todo"] == 0


class TestModelClasses:
    """Tests for data model classes."""

    def test_integrity_finding_as_dict(self):
        """Test IntegrityFinding.as_dict() serialization."""
        finding = IntegrityFinding(
            finding_id="test.skip.test_example",
            detector_id=DETECTOR_ID_SKIP_FOCUS,
            severity="medium",
            profile="release",
            affected_test_id="test_example",
            marker_kind="skip",
            reason="Test has skip marker without reason",
            owner=None,
            expiry=None,
            sourceRef="tests/test.py",
            readiness_effect="hold",
            suggested_manual_review_action="Add skip reason and owner",
        )

        d = finding.as_dict()

        # Canonical fields
        assert d["finding_id"] == "test.skip.test_example"
        assert d["detector_id"] == DETECTOR_ID_SKIP_FOCUS
        assert d["severity"] == "medium"
        assert d["profile"] == "release"
        assert d["affected_test_id"] == "test_example"
        assert d["marker_kind"] == "skip"
        assert d["reason"] == "Test has skip marker without reason"
        assert d["readiness_effect"] == "hold"
        assert d["suggested_manual_review_action"] == "Add skip reason and owner"

        # Compatibility aliases
        assert d["signal_id"] == "test_skip_detected"
        assert d["affected_refs"] == ["test_example"]
        assert d["product_effect"] == "hold"
        assert d["recommended_action"] == "Add skip reason and owner"
        assert d["sourceRefs"] == ["tests/test.py"]

    def test_integrity_risk_debt_as_dict(self):
        """Test IntegrityRiskDebt.as_dict() serialization."""
        debt = IntegrityRiskDebt(
            debt_id="debt_skip_test_example",
            debt_type="integrity_skip",
            severity="medium",
            status="open",
            test_id="test_example",
            marker="skip",
            owner=None,
            created_at="2026-06-29T12:00:00Z",
            last_seen_at="2026-06-29T12:00:00Z",
            age_days=0,
            source_refs=["tests/test.py"],
            recommended_actions=["Add skip reason"],
            blocking_profile=["release"],
        )

        d = debt.as_dict()

        assert d["debt_id"] == "debt_skip_test_example"
        assert d["debt_type"] == "integrity_skip"
        assert d["status"] == "open"
        assert d["owner"] is None
        assert d["blocking_profile"] == ["release"]

    def test_anti_evasion_match_as_dict(self):
        """Test AntiEvasionMatch.as_dict() serialization."""
        match = AntiEvasionMatch(
            pattern="jest_only",
            test_id="test_example",
            framework="jest",
            source_ref="tests/test.js",
        )

        d = match.as_dict()

        assert d["pattern"] == "jest_only"
        assert d["test_id"] == "test_example"
        assert d["framework"] == "jest"
        assert d["sourceRef"] == "tests/test.js"

    def test_signal_severity_matrix_has_required_profiles(self):
        """Test that SIGNAL_SEVERITY_MATRIX has all required profiles."""
        for signal_type in IntegritySignalType:
            profiles = SIGNAL_SEVERITY_MATRIX[signal_type]
            assert "default" in profiles
            assert "strict" in profiles
            assert "release" in profiles
            assert "product" in profiles

            for profile_config in profiles.values():
                assert "severity" in profile_config
                assert "effect" in profile_config


class TestProfileSeverityEscalation:
    """Tests for profile-dependent severity escalation."""

    def test_skip_escalates_in_release(self):
        """Skip severity escalates in release profile."""
        test_records = [{
            "canonical_test_id": "test_skip",
            "framework": "pytest",
            "status": "skipped",
            "skip": True,
            "sourceRefs": ["tests/test.py"],
        }]

        # Default profile
        findings_default, _ = detect_test_integrity_signals(
            test_records,
            profile="default",
        )

        # Release profile
        findings_release, _ = detect_test_integrity_signals(
            test_records,
            profile="release",
        )

        assert findings_default[0].severity == "low"
        assert findings_release[0].severity == "medium"
        assert findings_default[0].readiness_effect == "soft_gap"
        assert findings_release[0].readiness_effect == "hold"

    def test_only_blocked_in_product(self):
        """Only marker is blocked in product profile."""
        test_records = [{
            "canonical_test_id": "test_only",
            "framework": "jest",
            "status": "passed",
            "only": True,
            "sourceRefs": ["tests/test.js"],
        }]

        findings, _ = detect_test_integrity_signals(
            test_records,
            profile="product",
        )

        assert findings[0].readiness_effect == "blocked"
        assert findings[0].severity == "high"


class TestMultipleRecords:
    """Tests for handling multiple test records."""

    def test_multiple_findings_aggregated(self):
        """Multiple test records with multiple findings are aggregated."""
        test_records = [
            {
                "canonical_test_id": "test_skip_one",
                "framework": "pytest",
                "status": "skipped",
                "skip": True,
                "sourceRefs": ["tests/skip_one.py"],
            },
            {
                "canonical_test_id": "test_skip_two",
                "framework": "pytest",
                "status": "skipped",
                "skip": True,
                "sourceRefs": ["tests/skip_two.py"],
            },
            {
                "canonical_test_id": "test_only",
                "framework": "jest",
                "status": "passed",
                "only": True,
                "sourceRefs": ["tests/only.js"],
            },
        ]

        findings, anti_evasion = detect_test_integrity_signals(
            test_records,
            profile="release",
        )

        assert len(findings) == 3
        skip_findings = [f for f in findings if f.marker_kind == "skip"]
        only_findings = [f for f in findings if f.marker_kind == "only"]
        assert len(skip_findings) == 2
        assert len(only_findings) == 1

    def test_mixed_positive_negative_records(self):
        """Mixed positive and negative records are handled correctly."""
        test_records = [
            {
                "canonical_test_id": "test_clean",
                "framework": "pytest",
                "status": "passed",
                "sourceRefs": ["tests/clean.py"],
            },
            {
                "canonical_test_id": "test_skip_unjustified",
                "framework": "pytest",
                "status": "skipped",
                "skip": True,
                "sourceRefs": ["tests/skip.py"],
            },
        ]

        findings, _ = detect_test_integrity_signals(
            test_records,
            profile="release",
        )

        # Only the skip should generate a finding
        assert len(findings) == 1
        assert findings[0].marker_kind == "skip"


class TestPytestCollectionWarning:
    """Tests for pytest collection warning prevention."""

    def test_integrity_finding_not_collected_by_pytest(self):
        """IntegrityFinding must have __test__ = False to avoid pytest collection warning."""
        from hate.test_integrity.models import IntegrityFinding
        assert IntegrityFinding.__test__ is False

    def test_integrity_risk_debt_not_collected_by_pytest(self):
        """IntegrityRiskDebt must have __test__ = False to avoid pytest collection warning."""
        from hate.test_integrity.models import IntegrityRiskDebt
        assert IntegrityRiskDebt.__test__ is False

    def test_anti_evasion_match_not_collected_by_pytest(self):
        """AntiEvasionMatch must have __test__ = False to avoid pytest collection warning."""
        from hate.test_integrity.models import AntiEvasionMatch
        assert AntiEvasionMatch.__test__ is False