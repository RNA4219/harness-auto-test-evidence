"""Test coupling and manual review detector - HATE-PG-004C.

This module detects test integrity signals related to:
- implementation_test_coupling: production code branching on test/fixture names
- risk_without_oracle: high/critical risk without meaningful oracle
- coverage_without_evidence: coverage percentage alone as evidence
- manual_review_required: cases requiring human review

Per PRODUCT_GRADE_IMPLEMENTATION_SPEC.md Section 6:
- Production code should NOT branch on test/fixture names (anti-pattern)
- High/critical risk features MUST have oracle (expected value, contract, property, mutation)
- Coverage percentage alone is NOT meaningful evidence
- Manual review required for suspicious patterns
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from .coupling_types import (
    CI_MARKER_PATTERNS,
    DATA_DRIVEN_PARSER_PATTERNS,
    DETECTOR_ID_COUPLING,
    DETECTOR_ID_MANUAL_REVIEW,
    ENV_FLAG_PATTERNS,
    FIXTURE_NAME_BRANCH_PATTERNS,
    GOLDEN_FIXTURE_PATH_PATTERNS,
    STABLE_FIXTURE_MAPPING_PATTERNS,
    TEST_NAME_BRANCH_PATTERNS,
    CouplingClassification,
    CoverageClassification,
    ManualReviewClassification,
    OracleClassification,
)
from .coupling_findings import (
    CouplingFinding,
    CoverageEvidenceFinding,
    ManualReviewRequest,
    RiskOracleFinding,
)
from .models import (
    IntegrityRiskDebt,
)


def classify_coupling(code: str, test_id: str = "", fixture_names: list[str] = None) -> CouplingClassification:
    """Classify implementation-test coupling in code.

    Data-driven parsers and stable fixture mappings are NOT coupling.
    """
    if fixture_names is None:
        fixture_names = []

    code_lower = code.lower()

    # First check for actual coupling patterns (before false positive guards)
    # This ensures we detect coupling even if code looks like a parser/loader

    # Check for test name branching (coupling)
    for pattern in TEST_NAME_BRANCH_PATTERNS:
        if re.search(pattern, code_lower, re.IGNORECASE):
            return CouplingClassification.TEST_NAME_BRANCH

    # Check for fixture name branching (coupling)
    for pattern in FIXTURE_NAME_BRANCH_PATTERNS:
        if re.search(pattern, code_lower, re.IGNORECASE):
            return CouplingClassification.FIXTURE_NAME_BRANCH

    # Check for golden fixture path branching
    for pattern in GOLDEN_FIXTURE_PATH_PATTERNS:
        if re.search(pattern, code_lower, re.IGNORECASE):
            return CouplingClassification.GOLDEN_FIXTURE_PATH_BRANCH

    # Check for env flag branching (TEST_* env vars)
    for pattern in ENV_FLAG_PATTERNS:
        if re.search(pattern, code_lower, re.IGNORECASE):
            return CouplingClassification.ENV_FLAG_BRANCH

    # Now check for stable patterns (NOT coupling)
    for pattern in DATA_DRIVEN_PARSER_PATTERNS:
        if re.search(pattern, code_lower, re.IGNORECASE):
            # Already checked for coupling patterns above
            # If no coupling patterns matched, this is a data-driven parser
            return CouplingClassification.DATA_DRIVEN_PARSER

    for pattern in STABLE_FIXTURE_MAPPING_PATTERNS:
        if re.search(pattern, code_lower, re.IGNORECASE):
            # Already checked for coupling patterns above
            # If no coupling patterns matched, this is stable fixture mapping
            return CouplingClassification.STABLE_FIXTURE_MAPPING

    # Check for CI marker branching (acceptable for CI-specific behavior)
    # CI marker branching alone is NOT coupling if it's for CI-specific setup
    for pattern in CI_MARKER_PATTERNS:
        if re.search(pattern, code_lower, re.IGNORECASE):
            # CI-only branching is acceptable (not coupling)
            return CouplingClassification.NO_COUPLING

    return CouplingClassification.NO_COUPLING


def classify_oracle(evidence_records: list[dict[str, Any]]) -> OracleClassification:
    """Classify oracle presence in evidence records."""
    for record in evidence_records:
        record_type = record.get("record_type", "")
        payload = record.get("payload", record)

        # Check for expected value oracle
        if "expected" in str(payload).lower() or "expected_value" in str(payload).lower():
            return OracleClassification.EXPECTED_VALUE

        # Check for contract check oracle
        if record_type in ("contract_evidence", "contract") or "contract" in str(payload).lower():
            return OracleClassification.CONTRACT_CHECK

        # Check for property assertion oracle
        if "property" in str(payload).lower() or "@given" in str(payload).lower():
            return OracleClassification.PROPERTY_ASSERTION

        # Check for mutation score oracle
        if record_type in ("mutation_evidence", "mutation") or "mutation" in str(payload).lower():
            return OracleClassification.MUTATION_SCORE

        # Check for manual oracle (explicit human decision)
        if record.get("manual_oracle") or payload.get("manual_oracle"):
            return OracleClassification.MANUAL_ORACLE

    return OracleClassification.NO_ORACLE


def classify_coverage_evidence(coverage_record: dict[str, Any], evidence_records: list[dict[str, Any]]) -> CoverageClassification:
    """Classify coverage evidence quality."""
    payload = coverage_record.get("payload", coverage_record)

    coverage_percentage = payload.get("coverage_percentage", 0.0)
    covered_lines = payload.get("covered_lines", [])
    executed_tests = payload.get("executed_tests", [])

    has_oracle = classify_oracle(evidence_records) != OracleClassification.NO_ORACLE

    # Executed tests with meaningful oracle = good evidence
    if executed_tests and has_oracle:
        return CoverageClassification.EXECUTED_TESTS_WITH_ORACLE

    # Coverage percentage alone = not meaningful evidence
    if coverage_percentage and not executed_tests and not has_oracle:
        return CoverageClassification.COVERAGE_ONLY

    # Covered lines alone = not meaningful evidence
    if covered_lines and not executed_tests and not has_oracle:
        return CoverageClassification.COVERED_LINES_ONLY

    return CoverageClassification.NO_COVERAGE


def detect_implementation_test_coupling(
    production_sources: list[dict[str, Any]],
    *,
    fixture_id: str = "coupling-detector",
    profile: str = "default",
    now: str | None = None,
) -> list[CouplingFinding]:
    """Detect implementation-test coupling in production sources.

    Returns findings for:
    - Test name branching (production code branches on test names)
    - Fixture name branching (production code branches on fixture names)
    - Golden fixture path branching (production code branches on fixture paths)
    - ENV flag branching (production code branches on TEST_* env vars)
    """
    findings: list[CouplingFinding] = []
    current_time = now or datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    for prod_source in production_sources:
        file_path = prod_source.get("file_path", "")
        code = prod_source.get("code", "")
        source_ref = prod_source.get("source_ref", f"prod:{file_path}")
        test_ids = prod_source.get("test_ids", [])
        fixture_names = prod_source.get("fixture_names", [])

        classification = classify_coupling(code, test_ids[0] if test_ids else "", fixture_names)

        if classification == CouplingClassification.NO_COUPLING:
            continue

        # Data-driven parser and stable fixture mapping are NOT coupling
        if classification in {
            CouplingClassification.DATA_DRIVEN_PARSER,
            CouplingClassification.STABLE_FIXTURE_MAPPING,
        }:
            continue

        # Determine severity and effect
        # Production runtime behavior changing based on test/fixture names = hold or hard_dq
        if classification in {
            CouplingClassification.TEST_NAME_BRANCH,
            CouplingClassification.FIXTURE_NAME_BRANCH,
        }:
            severity = "high" if profile in ("release", "product") else "medium"
            effect = "hold" if profile in ("release", "product") else "soft_gap"
            manual_review = True
            human_decision = "verify_coupling_or_remove_branch"
        else:
            severity = "medium"
            effect = "soft_gap"
            manual_review = True
            human_decision = "verify_coupling_acceptable"

        finding_id = f"{fixture_id}.coupling.{file_path}.{classification.value}"

        findings.append(
            CouplingFinding(
                finding_id=finding_id,
                detector_id=DETECTOR_ID_COUPLING,
                evidence_class="implementation_test_coupling",
                triggering_records=[f"production:{file_path}"],
                source_refs=[source_ref],
                required_human_decision=human_decision,
                owner=None,
                expiry=None,
                readiness_effect=effect,
                risk_matrix_entry_ref=None,
                reason=f"Production code {file_path} branches on {classification.value.replace('_', ' ')}",
                severity=severity,
                profile=profile,
                manual_review_required=manual_review,
                classification=classification,
                confidence=0.90,
                affected_test_id=test_ids[0] if test_ids else "",
                affected_production_file=file_path,
            )
        )

    return findings


def detect_risk_without_oracle(
    risk_matrix_entries: list[dict[str, Any]],
    evidence_records: list[dict[str, Any]],
    *,
    fixture_id: str = "risk-oracle-detector",
    profile: str = "default",
    now: str | None = None,
) -> list[RiskOracleFinding]:
    """Detect high/critical risk features without meaningful oracle.

    Returns findings for:
    - High/critical risk without oracle = hold
    - Low/medium risk without oracle = risk debt or manual review
    """
    findings: list[RiskOracleFinding] = []
    current_time = now or datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    oracle_class = classify_oracle(evidence_records)

    for risk_entry in risk_matrix_entries:
        risk_id = risk_entry.get("risk_id", "")
        risk_level = risk_entry.get("risk_level", "low")
        feature_id = risk_entry.get("feature_id", "")
        source_refs = risk_entry.get("source_refs", [])

        # Only check high/critical risk features
        if risk_level not in ("high", "critical"):
            continue

        # Check if this risk has oracle
        has_oracle = False
        for record in evidence_records:
            record_risk_ref = record.get("risk_ref", record.get("risk_matrix_entry_ref", ""))
            if record_risk_ref == risk_id:
                record_oracle = classify_oracle([record])
                if record_oracle != OracleClassification.NO_ORACLE:
                    has_oracle = True
                    break

        if has_oracle:
            continue

        # High/critical risk without oracle = hold
        severity = risk_level
        effect = "hold" if profile in ("release", "product") else "soft_gap"
        manual_review = True
        human_decision = "add_oracle_or_accept_risk"

        finding_id = f"{fixture_id}.risk_without_oracle.{risk_id}"

        findings.append(
            RiskOracleFinding(
                finding_id=finding_id,
                detector_id=DETECTOR_ID_COUPLING,
                evidence_class="risk_without_oracle",
                triggering_records=[f"risk:{risk_id}"],
                source_refs=source_refs if source_refs else [f"risk:{risk_id}"],
                required_human_decision=human_decision,
                owner=None,
                expiry=None,
                readiness_effect=effect,
                risk_matrix_entry_ref=risk_id,
                reason=f"High/critical risk {risk_id} has execution/coverage but no oracle",
                severity=severity,
                profile=profile,
                manual_review_required=manual_review,
                risk_level=risk_level,
                oracle_classification=OracleClassification.NO_ORACLE,
                confidence=0.85,
            )
        )

    return findings


def detect_coverage_without_evidence(
    coverage_records: list[dict[str, Any]],
    evidence_records: list[dict[str, Any]],
    risk_matrix_entries: list[dict[str, Any]],
    *,
    fixture_id: str = "coverage-evidence-detector",
    profile: str = "default",
    now: str | None = None,
) -> list[CoverageEvidenceFinding]:
    """Detect coverage without meaningful evidence.

    Returns findings for:
    - Coverage percentage alone = not meaningful evidence
    - Covered lines alone = not meaningful evidence
    - Executed tests + oracle = pass/soft_gap
    - Required high-risk sole evidence is coverage = hold/hard_dq
    """
    findings: list[CoverageEvidenceFinding] = []
    current_time = now or datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    for coverage_record in coverage_records:
        coverage_id = coverage_record.get("coverage_id", coverage_record.get("record_id", ""))
        payload = coverage_record.get("payload", coverage_record)
        source_refs = coverage_record.get("source_refs", payload.get("sourceRefs", []))

        classification = classify_coverage_evidence(coverage_record, evidence_records)

        # Executed tests with oracle = good evidence (soft_gap at most)
        if classification == CoverageClassification.EXECUTED_TESTS_WITH_ORACLE:
            # Check if this coverage is sole evidence for required high-risk
            risk_ref = payload.get("risk_ref", "")
            if risk_ref:
                risk_entry = next(
                    (r for r in risk_matrix_entries if r.get("risk_id") == risk_ref),
                    None
                )
                if risk_entry and risk_entry.get("risk_level") in ("high", "critical"):
                    # Check if coverage is sole evidence
                    other_evidence = [
                        e for e in evidence_records
                        if e.get("risk_ref", e.get("risk_matrix_entry_ref", "")) == risk_ref
                        and e.get("record_type") not in ("coverage", "coverage_slice")
                    ]
                    if not other_evidence:
                        # Sole evidence is coverage only (even with oracle)
                        severity = "high"
                        effect = "hold"
                        manual_review = True
                    else:
                        severity = "low"
                        effect = "soft_gap"
                        manual_review = False
                else:
                    severity = "low"
                    effect = "soft_gap"
                    manual_review = False
            else:
                severity = "low"
                effect = "soft_gap"
                manual_review = False
        else:
            # Coverage only or covered lines only = not meaningful
            severity = "medium"
            effect = "hold" if profile in ("release", "product") else "soft_gap"
            manual_review = True

        # Check if required high-risk sole evidence is coverage
        risk_ref = payload.get("risk_ref", "")
        if risk_ref and classification in {
            CoverageClassification.COVERAGE_ONLY,
            CoverageClassification.COVERED_LINES_ONLY,
        }:
            risk_entry = next(
                (r for r in risk_matrix_entries if r.get("risk_id") == risk_ref),
                None
            )
            if risk_entry and risk_entry.get("risk_level") in ("high", "critical"):
                severity = "high"
                effect = "hold"
                manual_review = True

        finding_id = f"{fixture_id}.coverage_without_evidence.{coverage_id}"

        coverage_percentage = payload.get("coverage_percentage", 0.0)
        executed_tests = payload.get("executed_tests", [])
        has_oracle = classification == CoverageClassification.EXECUTED_TESTS_WITH_ORACLE

        findings.append(
            CoverageEvidenceFinding(
                finding_id=finding_id,
                detector_id=DETECTOR_ID_COUPLING,
                evidence_class="coverage_without_evidence",
                triggering_records=[f"coverage:{coverage_id}"],
                source_refs=source_refs if source_refs else [f"coverage:{coverage_id}"],
                required_human_decision="add_oracle_or_accept_coverage_only",
                owner=None,
                expiry=None,
                readiness_effect=effect,
                risk_matrix_entry_ref=risk_ref if risk_ref else None,
                reason=f"Coverage {coverage_id} is coverage-only without meaningful oracle",
                severity=severity,
                profile=profile,
                manual_review_required=manual_review,
                coverage_classification=classification,
                coverage_percentage=coverage_percentage,
                has_executed_tests=bool(executed_tests),
                has_oracle=has_oracle,
                confidence=0.80,
            )
        )

    return findings


def build_coupling_integrity_report(
    production_sources: list[dict[str, Any]],
    risk_matrix_entries: list[dict[str, Any]],
    evidence_records: list[dict[str, Any]],
    coverage_records: list[dict[str, Any]],
    *,
    fixture_id: str = "coupling-detector",
    profile: str = "default",
    now: str | None = None,
) -> dict[str, Any]:
    """Build complete test integrity report for coupling signals.

    Per PRODUCT_GRADE_IMPLEMENTATION_SPEC.md Section 6.3:
    - implementation_test_coupling: hold or hard_dq if production branches on test/fixture names
    - risk_without_oracle: hold for high/critical risk without oracle
    - coverage_without_evidence: soft_gap when supplementary, hold/hard_dq when sole required evidence
    """
    current_time = now or datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    # Detect signals
    coupling_findings = detect_implementation_test_coupling(
        production_sources,
        fixture_id=fixture_id,
        profile=profile,
        now=current_time,
    )
    risk_oracle_findings = detect_risk_without_oracle(
        risk_matrix_entries,
        evidence_records,
        fixture_id=fixture_id,
        profile=profile,
        now=current_time,
    )
    coverage_findings = detect_coverage_without_evidence(
        coverage_records,
        evidence_records,
        risk_matrix_entries,
        fixture_id=fixture_id,
        profile=profile,
        now=current_time,
    )

    # Build combined findings list
    all_findings: list[dict[str, Any]] = []
    for cf in coupling_findings:
        all_findings.append(cf.as_dict())
    for rf in risk_oracle_findings:
        all_findings.append(rf.as_dict())
    for cvf in coverage_findings:
        all_findings.append(cvf.as_dict())

    # Generate risk debt for non-pass findings
    risk_debt: list[IntegrityRiskDebt] = []
    for finding in all_findings:
        effect = finding.get("readiness_effect", "pass")
        if effect == "pass":
            continue

        debt_type = finding.get("evidence_class", "unknown")
        debt_id = finding.get("finding_id", "").replace("finding", "debt")

        blocking_profile = []
        if effect == "hold":
            blocking_profile = ["release", "product"]
        elif effect == "blocked":
            blocking_profile = ["release", "product"]

        risk_debt.append(
            IntegrityRiskDebt(
                debt_id=debt_id,
                debt_type=debt_type,
                severity=finding.get("severity", "medium"),
                status="open",
                test_id=finding.get("affected_test_id", ""),
                marker=debt_type,
                owner=finding.get("owner"),
                created_at=current_time,
                last_seen_at=current_time,
                age_days=0,
                source_refs=finding.get("sourceRefs", []),
                recommended_actions=[
                    finding.get("required_human_decision", "resolve_finding"),
                ],
                blocking_profile=blocking_profile,
                justification=None,
                expiry_date=finding.get("expiry"),
            )
        )

    # Aggregate source refs
    all_refs = set()
    for f in all_findings:
        for ref in f.get("sourceRefs", []):
            all_refs.add(ref)
    for d in risk_debt:
        for ref in d.source_refs:
            all_refs.add(ref)

    # Compute summary
    blocked_count = sum(1 for f in all_findings if f.get("readiness_effect") == "blocked")
    hold_count = sum(1 for f in all_findings if f.get("readiness_effect") == "hold")
    soft_gap_count = sum(1 for f in all_findings if f.get("readiness_effect") == "soft_gap")
    pass_count = sum(1 for f in all_findings if f.get("readiness_effect") == "pass")

    # Count by evidence class
    coupling_count = len(coupling_findings)
    risk_oracle_count = len(risk_oracle_findings)
    coverage_count = len(coverage_findings)

    # Overall status
    if blocked_count > 0:
        overall_status = "blocked"
    elif hold_count > 0:
        overall_status = "hold"
    elif soft_gap_count > 0:
        overall_status = "soft_gap"
    else:
        overall_status = "pass"

    summary = {
        "overall_status": overall_status,
        "finding_count": len(all_findings),
        "blocked_count": blocked_count,
        "hold_count": hold_count,
        "soft_gap_count": soft_gap_count,
        "pass_count": pass_count,
        "debt_count": len(risk_debt),
        "open_debt_count": sum(1 for d in risk_debt if d.status == "open"),
        "by_signal_type": {
            "implementation_test_coupling": coupling_count,
            "risk_without_oracle": risk_oracle_count,
            "coverage_without_evidence": coverage_count,
        },
        "profile_effect": profile,
    }

    return {
        "schema_version": "HATE/v1",
        "record_type": "test_integrity_report",
        "fixture_id": fixture_id,
        "profile": profile,
        "summary": summary,
        "findings": sorted(all_findings, key=lambda x: (x.get("severity", ""), x.get("finding_id", ""))),
        "test_coupling_findings": [cf.as_dict() for cf in coupling_findings],
        "risk_oracle_findings": [rf.as_dict() for rf in risk_oracle_findings],
        "coverage_evidence_findings": [cvf.as_dict() for cvf in coverage_findings],
        "risk_debt": [d.as_dict() for d in sorted(risk_debt, key=lambda x: (x.severity, x.debt_id))],
        "sourceRefs": sorted(all_refs),
    }
