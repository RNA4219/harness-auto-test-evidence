"""Mock abuse and assertion quality detector - HATE-PG-004B.

This module detects test integrity signals related to:
- Mock abuse: excessive mocks, empty stubs, mocks replacing behavior under test
- Assertion quality: tests without meaningful assertions, trivial assertions, snapshot-only

Per PRODUCT_GRADE_IMPLEMENTATION_SPEC.md Section 6:
- mock_abuse_detected: excessive mocks, empty stubs, always-success fakes, mocks inside non-boundary code
- assertion_quality: tests execute code without meaningful assertions, assert only truthity, snapshots only
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .mock_assertion_types import (
    EMPTY_STUB_PATTERNS,
    EXTERNAL_BOUNDARY_PATTERNS,
    INTERNAL_DOMAIN_PATTERNS,
    NO_EXCEPTION_ONLY_PATTERNS,
    SNAPSHOT_ONLY_PATTERNS,
    TRIVIAL_ASSERTION_PATTERNS,
    AssertionClassification,
    MockClassification,
)
from .models import (
    IntegrityRiskDebt,
    IntegritySignalType,
    READINESS_EFFECTS,
    SEVERITY_LEVELS,
    SIGNAL_SEVERITY_MATRIX,
)


@dataclass(frozen=True)
class MockFinding:
    """Finding for mock abuse detection."""
    __test__ = False  # Prevent pytest from collecting this as a test class

    test_id: str
    mock_target: str
    classification: MockClassification
    confidence: float
    reason: str
    source_ref: str
    line_number: int | None
    framework: str
    language: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "test_id": self.test_id,
            "mock_target": self.mock_target,
            "classification": self.classification.value,
            "confidence": self.confidence,
            "reason": self.reason,
            "sourceRef": self.source_ref,
            "line_number": self.line_number,
            "framework": self.framework,
            "language": self.language,
        }


@dataclass(frozen=True)
class AssertionFinding:
    """Finding for assertion quality detection."""
    __test__ = False  # Prevent pytest from collecting this as a test class

    test_id: str
    assertion_type: AssertionClassification
    confidence: float
    reason: str
    source_ref: str
    line_number: int | None
    framework: str
    language: str
    has_domain_oracle: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "test_id": self.test_id,
            "assertion_type": self.assertion_type.value,
            "confidence": self.confidence,
            "reason": self.reason,
            "sourceRef": self.source_ref,
            "line_number": self.line_number,
            "framework": self.framework,
            "language": self.language,
            "has_domain_oracle": self.has_domain_oracle,
        }


@dataclass(frozen=True)
class TestIntegrityReport:
    """Complete test integrity report for mock/assertion signals."""
    __test__ = False  # Prevent pytest from collecting this as a test class

    schema_version: str
    record_type: str
    fixture_id: str
    profile: str
    summary: dict[str, Any]
    mock_abuse_findings: list[MockFinding]
    assertion_quality_findings: list[AssertionFinding]
    findings: list[dict[str, Any]]
    risk_debt: list[IntegrityRiskDebt]
    source_refs: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "record_type": self.record_type,
            "fixture_id": self.fixture_id,
            "profile": self.profile,
            "summary": self.summary,
            "mock_abuse_findings": [f.as_dict() for f in self.mock_abuse_findings],
            "assertion_quality_findings": [f.as_dict() for f in self.assertion_quality_findings],
            "findings": self.findings,
            "risk_debt": [d.as_dict() for d in self.risk_debt],
            "sourceRefs": self.source_refs,
        }


def classify_mock(target: str, context: str = "") -> MockClassification:
    """Classify a mock based on its target and context.

    External boundary mocks are legitimate; internal domain mocks are suspicious.
    Priority: External boundary keywords in target > Internal domain keywords in target > Context keywords.
    """
    target_lower = target.lower()
    context_lower = context.lower()

    # External boundary keywords - these components are infrastructure/system boundaries
    external_boundary_keywords = {
        "http", "api", "network", "client", "socket", "url", "web",
        "file", "filesystem", "fs", "path", "io", "disk",
        "time", "clock", "datetime", "date", "timer", "schedule",
        "random", "seed", "rng",
        "secret", "credential", "token", "key", "auth", "password",
        "external", "thirdparty", "third_party", "vendor",
        "platform", "os", "env", "config", "settings",
        "database", "db", "sql", "mongo", "redis", "postgres",
        "queue", "kafka", "mq", "broker", "event",
        "cache", "storage", "s3", "bucket", "cloud",
        "email", "sms", "notification", "push",
        "payment", "stripe", "paypal",
    }

    # Check for external boundary patterns in target name FIRST (highest priority)
    for keyword in external_boundary_keywords:
        if keyword in target_lower:
            return MockClassification.EXTERNAL_BOUNDARY

    # Internal domain keywords - these are domain logic components that should NOT be mocked
    internal_domain_keywords = {
        "service", "handler", "controller", "repository", "domain", "logic",
        "calculator", "validator", "processor", "manager", "engine", "builder",
        "factory", "converter", "transformer", "mapper", "aggregator",
        "helper", "util", "assistant",
    }

    # Check for internal domain patterns in target name
    for keyword in internal_domain_keywords:
        if keyword in target_lower:
            return MockClassification.INTERNAL_DOMAIN

    # Check for external boundary keywords in context
    for keyword in external_boundary_keywords:
        if keyword in context_lower:
            return MockClassification.EXTERNAL_BOUNDARY

    # Check for external boundary patterns via regex
    for boundary_type, patterns in EXTERNAL_BOUNDARY_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, target_lower, re.IGNORECASE):
                return MockClassification.EXTERNAL_BOUNDARY
            if re.search(pattern, context_lower, re.IGNORECASE):
                return MockClassification.EXTERNAL_BOUNDARY

    # Check for internal domain patterns via regex
    for pattern in INTERNAL_DOMAIN_PATTERNS:
        if re.search(pattern, target_lower, re.IGNORECASE):
            return MockClassification.INTERNAL_DOMAIN

    return MockClassification.UNKNOWN


def classify_assertion(assertion_text: str, test_body: str = "") -> AssertionClassification:
    """Classify assertion quality based on the assertion content.

    Meaningful assertions verify expected behavior; trivial ones don't.
    """
    assertion_lower = assertion_text.lower()
    test_body_lower = test_body.lower()

    # Check for no-exception-only patterns first (even if assertion is empty)
    for pattern in NO_EXCEPTION_ONLY_PATTERNS:
        if re.search(pattern, test_body_lower, re.IGNORECASE):
            return AssertionClassification.NO_EXCEPTION_ONLY

    # Check for missing assertions
    if not assertion_text or assertion_text.strip() == "":
        return AssertionClassification.MISSING

    # Check for trivial assertions
    for pattern in TRIVIAL_ASSERTION_PATTERNS:
        if re.search(pattern, assertion_lower, re.IGNORECASE):
            return AssertionClassification.TRIVIAL

    # Check for constant assertions (x == x, etc.)
    # Pattern: assert var == var (same variable compared to itself)
    match = re.search(r"assert\s+(\w+)\s*==\s+(\w+)", assertion_text)
    if match and match.group(1) == match.group(2):
        return AssertionClassification.CONSTANT

    # Check for snapshot-only patterns
    for pattern in SNAPSHOT_ONLY_PATTERNS:
        if re.search(pattern, assertion_lower, re.IGNORECASE):
            # Check if there's also a semantic guard (role-based, text-based, or property-based)
            # First, check for negation patterns that indicate NO semantic guard
            negation_patterns = [
                r"no\s*semantic",
                r"without\s*semantic",
                r"only\s*snapshot",
                r"just\s*snapshot",
            ]
            has_negation = any(re.search(p, test_body_lower, re.IGNORECASE) for p in negation_patterns)

            semantic_indicators = [
                "property", "behavior", "expected", "domain",
                "getbyrole", "getbytext", "getbylabel", "getbytestid",
                "toHaveText", "toHaveValue", "toContain", "toBeVisible",
                "toBeTruthy", "toBeFalsy", "toEqual", "toBe",
                "== expected", "== '\"",  # actual comparison assertions
            ]
            has_semantic_guard = any(ind in test_body_lower for ind in semantic_indicators)

            # Return MEANINGFUL only if semantic guard exists AND not negated
            if has_semantic_guard and not has_negation:
                return AssertionClassification.MEANINGFUL
            return AssertionClassification.SNAPSHOT_ONLY

    return AssertionClassification.MEANINGFUL


def detect_empty_stub(code: str) -> bool:
    """Detect if code is an empty stub (pass, ..., returning None)."""
    for pattern in EMPTY_STUB_PATTERNS:
        if re.search(pattern, code, re.IGNORECASE):
            return True
    return False


def has_domain_oracle(test_body: str) -> bool:
    """Check if test has a domain oracle (property assertion, expected value check)."""
    domain_patterns = [
        r"assert\s+\w+\s*==\s*expected",
        r"assert\s+\w+\s*!=\s*expected",
        r"assert\s+\w+\s*in\s*\[",
        r"assert\s+\w+\s*>=\s*\d+",
        r"assert\s+\w+\s*<=\s*\d+",
        r"assert\s+\w+\s*>\s*\d+",
        r"assert\s+\w+\s*<\s*\d+",
        r"assert\s+\w+\s*==\s*['\"]",  # string comparison
        r"assert\s+\w+\s*is\s+True",
        r"assert\s+\w+\s*is\s+False",
        r"assert\s+result",
        r"assert\s+output",
        r"assert\s+response",
        r"property\s*\(",
        r"@given",
        r"hypothesis",
        r"pytest\.param",
        r"expected_",
    ]
    for pattern in domain_patterns:
        if re.search(pattern, test_body, re.IGNORECASE):
            return True
    return False


def detect_fixture_name_coupling(mock_code: str, test_id: str) -> bool:
    """Detect if mock returns the test/fixture name itself.

    This creates coupling between test identity and mock behavior,
    which is an anti-pattern because the test passes only because
    the mock knows the test's name.
    """
    if not mock_code or not test_id:
        return False

    # Check if mock_code contains test_id as a return value
    mock_code_lower = mock_code.lower()

    # Pattern: return_value = 'test_id' or return_value = "test_id"
    patterns = [
        rf"return_value\s*=\s*['\"]\s*{re.escape(test_id)}\s*['\"]",
        rf"return_value\s*=\s*{re.escape(test_id)}",
        rf"['\"]\s*{re.escape(test_id)}\s*['\"]",
    ]

    for pattern in patterns:
        if re.search(pattern, mock_code_lower, re.IGNORECASE):
            return True

    return False


def detect_mock_abuse_signals(
    test_sources: list[dict[str, Any]],
    *,
    fixture_id: str = "mock-assertion-detector",
    profile: str = "default",
    now: str | None = None,
) -> list[MockFinding]:
    """Detect mock abuse signals from test sources.

    Returns findings for:
    - Internal domain mocks (replacing behavior under test)
    - Empty stubs (pass, ..., returning None)
    - Fixture name coupling (mock returns test name)
    """
    findings: list[MockFinding] = []

    for test_source in test_sources:
        test_id = test_source.get("test_id", "")
        code = test_source.get("code", "")
        language = test_source.get("language", "python")
        framework = test_source.get("framework", "pytest")
        source_ref = test_source.get("source_ref", f"test:{test_id}")
        mock_targets = test_source.get("mock_targets", [])

        # Check each mock target
        for mock_info in mock_targets:
            target = mock_info.get("target", "")
            line_number = mock_info.get("line_number")
            context = mock_info.get("context", "")
            mock_code = mock_info.get("mock_code", "")

            classification = classify_mock(target, context)

            if classification == MockClassification.INTERNAL_DOMAIN:
                findings.append(
                    MockFinding(
                        test_id=test_id,
                        mock_target=target,
                        classification=classification,
                        confidence=0.85,
                        reason=f"Mock replaces internal domain logic '{target}' - behavior under test is mocked",
                        source_ref=source_ref,
                        line_number=line_number,
                        framework=framework,
                        language=language,
                    )
                )

            # Check for empty stubs in the mock setup
            if detect_empty_stub(mock_code):
                findings.append(
                    MockFinding(
                        test_id=test_id,
                        mock_target=target,
                        classification=MockClassification.EMPTY_STUB,
                        confidence=0.90,
                        reason=f"Empty stub detected for '{target}' - no behavior defined",
                        source_ref=source_ref,
                        line_number=line_number,
                        framework=framework,
                        language=language,
                    )
                )

            # Check for fixture name coupling (mock returns test name)
            if detect_fixture_name_coupling(mock_code, test_id):
                findings.append(
                    MockFinding(
                        test_id=test_id,
                        mock_target=target,
                        classification=MockClassification.FIXTURE_NAME_COUPLING,
                        confidence=0.95,
                        reason=f"Fixture name coupling detected - mock returns test name '{test_id}'",
                        source_ref=source_ref,
                        line_number=line_number,
                        framework=framework,
                        language=language,
                    )
                )

    return findings


def detect_assertion_quality_signals(
    test_sources: list[dict[str, Any]],
    *,
    fixture_id: str = "mock-assertion-detector",
    profile: str = "default",
    now: str | None = None,
) -> list[AssertionFinding]:
    """Detect assertion quality signals from test sources.

    Returns findings for:
    - Trivial assertions (assert True, constant comparisons)
    - No-exception-only tests
    - Snapshot-only tests without semantic guard
    - Missing assertions
    """
    findings: list[AssertionFinding] = []

    for test_source in test_sources:
        test_id = test_source.get("test_id", "")
        code = test_source.get("code", "")
        language = test_source.get("language", "python")
        framework = test_source.get("framework", "pytest")
        source_ref = test_source.get("source_ref", f"test:{test_id}")
        assertions = test_source.get("assertions", [])

        # If no assertions section, analyze full code
        if not assertions:
            classification = classify_assertion("", code)
            if classification != AssertionClassification.MEANINGFUL:
                findings.append(
                    AssertionFinding(
                        test_id=test_id,
                        assertion_type=classification,
                        confidence=0.75,
                        reason=f"No meaningful assertions found in test body",
                        source_ref=source_ref,
                        line_number=None,
                        framework=framework,
                        language=language,
                        has_domain_oracle=has_domain_oracle(code),
                    )
                )
            continue

        for assertion_info in assertions:
            assertion_text = assertion_info.get("text", "")
            line_number = assertion_info.get("line_number")

            classification = classify_assertion(assertion_text, code)

            if classification != AssertionClassification.MEANINGFUL:
                confidence = 0.80 if classification in {
                    AssertionClassification.TRIVIAL,
                    AssertionClassification.CONSTANT,
                } else 0.70

                reason_map = {
                    AssertionClassification.TRIVIAL: "Trivial assertion detected - does not verify meaningful behavior",
                    AssertionClassification.CONSTANT: "Constant assertion detected - compares same value to itself",
                    AssertionClassification.NO_EXCEPTION_ONLY: "Test only verifies no exception raised - lacks oracle",
                    AssertionClassification.SNAPSHOT_ONLY: "Snapshot-only assertion without semantic guard",
                    AssertionClassification.MISSING: "No assertion found in test body",
                }

                findings.append(
                    AssertionFinding(
                        test_id=test_id,
                        assertion_type=classification,
                        confidence=confidence,
                        reason=reason_map.get(classification, "Assertion quality issue"),
                        source_ref=source_ref,
                        line_number=line_number,
                        framework=framework,
                        language=language,
                        has_domain_oracle=has_domain_oracle(code),
                    )
                )

    return findings


def build_test_integrity_report(
    test_sources: list[dict[str, Any]],
    *,
    fixture_id: str = "mock-assertion-detector",
    profile: str = "default",
    now: str | None = None,
    boundary_manifest: list[str] | None = None,
) -> TestIntegrityReport:
    """Build complete test integrity report for mock/assertion signals.

    Per PRODUCT_GRADE_IMPLEMENTATION_SPEC.md Section 6.3:
    - mock_abuse_detected at external boundary with domain oracle: soft_gap/conditional
    - mock_abuse_detected replacing behavior under test: hold/hard_dq
    - assertion_quality weak in non-risk: soft_gap/conditional
    - assertion_quality no oracle for required risk: hold/hard_dq
    """
    current_time = now or datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    # Detect signals
    mock_findings = detect_mock_abuse_signals(
        test_sources,
        fixture_id=fixture_id,
        profile=profile,
        now=current_time,
    )
    assertion_findings = detect_assertion_quality_signals(
        test_sources,
        fixture_id=fixture_id,
        profile=profile,
        now=current_time,
    )

    # Get severity/effect matrix for profile
    profile_matrix = SIGNAL_SEVERITY_MATRIX.get(IntegritySignalType.MOCK_ABUSE_DETECTED, {}).get(profile, {})
    assertion_matrix = SIGNAL_SEVERITY_MATRIX.get(IntegritySignalType.ASSERTION_QUALITY, {}).get(profile, {})

    # Build report findings
    report_findings: list[dict[str, Any]] = []
    risk_debt: list[IntegrityRiskDebt] = []

    # Process mock findings
    for mf in mock_findings:
        # Check if mock is at declared external boundary
        is_boundary_declared = boundary_manifest and any(
            b.lower() in mf.mock_target.lower() for b in boundary_manifest
        )

        # Determine severity and effect based on classification
        if mf.classification == MockClassification.EXTERNAL_BOUNDARY or is_boundary_declared:
            severity = "low"
            effect = "soft_gap"
            manual_review = False
        elif mf.classification == MockClassification.INTERNAL_DOMAIN:
            severity = profile_matrix.get("severity", "high")
            effect = profile_matrix.get("effect", "blocked")
            manual_review = True
        elif mf.classification == MockClassification.EMPTY_STUB:
            severity = "medium"
            effect = "hold"
            manual_review = True
        else:
            severity = "medium"
            effect = "conditional"
            manual_review = True

        signal_id = IntegritySignalType.MOCK_ABUSE_DETECTED.value
        report_findings.append({
            "signal_id": signal_id,
            "severity": severity,
            "affected_refs": [mf.test_id],
            "reason": mf.reason,
            "recommended_action": "Replace mock with real implementation or add domain oracle",
            "product_effect": {
                "aete_dimension": "oracle_strength",
                "decision_impact": effect,
                "manual_review": manual_review,
            },
            "sourceRefs": [mf.source_ref],
            "confidence": mf.confidence,
            "detector_rule": f"mock_classification:{mf.classification.value}",
            "language": mf.language,
            "framework": mf.framework,
        })

        # Generate risk debt for blocking findings
        if effect in {"blocked", "hold"}:
            risk_debt.append(
                IntegrityRiskDebt(
                    debt_id=f"debt_mock_{mf.test_id}_{mf.mock_target}",
                    debt_type="mock_abuse",
                    severity=severity,
                    status="open",
                    test_id=mf.test_id,
                    marker=mf.mock_target,
                    owner=None,
                    created_at=current_time,
                    last_seen_at=current_time,
                    age_days=0,
                    source_refs=[mf.source_ref],
                    recommended_actions=[
                        "Replace mock with real implementation",
                        "Add domain oracle to verify behavior",
                        "Declare boundary in manifest if external",
                    ],
                    blocking_profile=[profile] if effect == "blocked" else [],
                )
            )

    # Process assertion findings
    for af in assertion_findings:
        # Determine severity and effect based on classification
        if af.assertion_type == AssertionClassification.MEANINGFUL:
            continue  # Skip meaningful assertions

        if af.has_domain_oracle:
            severity = "low"
            effect = "soft_gap"
            manual_review = False
        elif af.assertion_type in {
            AssertionClassification.TRIVIAL,
            AssertionClassification.CONSTANT,
            AssertionClassification.NO_EXCEPTION_ONLY,
        }:
            severity = assertion_matrix.get("severity", "medium")
            effect = assertion_matrix.get("effect", "conditional")
            manual_review = True
        elif af.assertion_type == AssertionClassification.SNAPSHOT_ONLY:
            severity = "medium"
            effect = "hold" if profile in {"release", "product"} else "soft_gap"
            manual_review = True
        else:  # MISSING
            severity = "high"
            effect = "blocked"
            manual_review = True

        signal_id = IntegritySignalType.ASSERTION_QUALITY.value
        report_findings.append({
            "signal_id": signal_id,
            "severity": severity,
            "affected_refs": [af.test_id],
            "reason": af.reason,
            "recommended_action": "Add meaningful assertion that verifies expected behavior",
            "product_effect": {
                "aete_dimension": "oracle_strength",
                "decision_impact": effect,
                "manual_review": manual_review,
            },
            "sourceRefs": [af.source_ref],
            "confidence": af.confidence,
            "detector_rule": f"assertion_classification:{af.assertion_type.value}",
            "language": af.language,
            "framework": af.framework,
        })

        # Generate risk debt for blocking findings
        if effect in {"blocked", "hold"}:
            risk_debt.append(
                IntegrityRiskDebt(
                    debt_id=f"debt_assertion_{af.test_id}",
                    debt_type="assertion_weak",
                    severity=severity,
                    status="open",
                    test_id=af.test_id,
                    marker=af.assertion_type.value,
                    owner=None,
                    created_at=current_time,
                    last_seen_at=current_time,
                    age_days=0,
                    source_refs=[af.source_ref],
                    recommended_actions=[
                        "Add meaningful assertion",
                        "Add property-based oracle",
                        "Add contract check",
                    ],
                    blocking_profile=[profile] if effect == "blocked" else [],
                )
            )

    # Compute summary
    overall_status = _compute_overall_status(report_findings, profile)

    summary = {
        "overall_status": overall_status,
        "mock_abuse_count": len(mock_findings),
        "assertion_quality_count": len(assertion_findings),
        "blocked_count": sum(1 for f in report_findings if f["product_effect"]["decision_impact"] == "blocked"),
        "hold_count": sum(1 for f in report_findings if f["product_effect"]["decision_impact"] == "hold"),
        "soft_gap_count": sum(1 for f in report_findings if f["product_effect"]["decision_impact"] == "soft_gap"),
        "manual_review_count": sum(1 for f in report_findings if f["product_effect"]["manual_review"]),
        "risk_debt_count": len(risk_debt),
    }

    # Collect source refs
    source_refs = sorted({
        ref
        for f in report_findings
        for ref in f.get("sourceRefs", [])
    })

    return TestIntegrityReport(
        schema_version="HATE/v1",
        record_type="test_integrity_report",
        fixture_id=fixture_id,
        profile=profile,
        summary=summary,
        mock_abuse_findings=mock_findings,
        assertion_quality_findings=assertion_findings,
        findings=report_findings,
        risk_debt=risk_debt,
        source_refs=source_refs,
    )


def _compute_overall_status(findings: list[dict[str, Any]], profile: str) -> str:
    """Compute overall status from findings."""
    if not findings:
        return "pass"

    # Check for blocked findings
    blocked = any(f["product_effect"]["decision_impact"] == "blocked" for f in findings)
    if blocked:
        return "blocked"

    # Check for hold findings
    hold = any(f["product_effect"]["decision_impact"] == "hold" for f in findings)
    if hold:
        return "hold"

    # Check for soft_gap
    soft_gap = any(f["product_effect"]["decision_impact"] == "soft_gap" for f in findings)
    if soft_gap:
        return "soft_gap"

    return "pass"
