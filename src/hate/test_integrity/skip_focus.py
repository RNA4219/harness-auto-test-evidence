"""Skip/focus/todo detector implementation - HATE-PG-004A.

Consumes normalized test_result records and detects integrity signals:
- skip markers without owner/reason
- xfail markers without expiry or issue ref
- only/focus markers (anti-evasion for framework variants)
- todo markers in release profile

Outputs test-integrity-report.json with findings, risk_debt, and sourceRefs.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from .models import (
    AntiEvasionMatch,
    IntegrityFinding,
    IntegrityRiskDebt,
    IntegritySignalType,
    DETECTOR_ID_SKIP_FOCUS,
    SIGNAL_SEVERITY_MATRIX,
)

# Anti-evasion patterns per framework
# From PRODUCT_GRADE_IMPLEMENTATION_SPEC.md anti-evasion rules
ANTI_EVASION_PATTERNS = {
    "jest": [
        (r"\.only\b", "jest_only"),
        (r"fit\s*\(", "jest_fit_focus"),
        (r"fdescribe\s*\(", "jest_fdescribe_focus"),
    ],
    "vitest": [
        (r"\.only\b", "vitest_only"),
        (r"\.skip\b", "vitest_skip"),
        (r"\.todo\b", "vitest_todo"),
    ],
    "pytest": [
        (r"@pytest\.mark\.skip", "pytest_mark_skip"),
        (r"@pytest\.mark\.xfail", "pytest_mark_xfail"),
        (r"-k\s+", "pytest_filter_narrowing"),
    ],
    "mocha": [
        (r"\.only\b", "mocha_only"),
        (r"it\.only\s*\(", "mocha_it_only"),
        (r"describe\.only\s*\(", "mocha_describe_only"),
    ],
}


def detect_test_integrity_signals(
    test_records: list[dict[str, Any]],
    *,
    profile: str = "default",
    now: str | None = None,
    fixture_id: str = "test-integrity-skip-focus",
) -> tuple[list[IntegrityFinding], list[AntiEvasionMatch]]:
    """Detect test integrity signals from normalized test_result records.

    Args:
        test_records: List of test_result payload dicts (normalized records)
        profile: Profile context (default, strict, release, product)
        now: ISO timestamp for current time
        fixture_id: Identifier for the report

    Returns:
        Tuple of (findings, anti_evasion_matches)
    """
    current_time = now or datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    findings: list[IntegrityFinding] = []
    anti_evasion_matches: list[AntiEvasionMatch] = []

    for record in test_records:
        payload = record.get("payload", record)
        test_id = payload.get("canonical_test_id", "")
        framework = payload.get("framework", "unknown")
        status = payload.get("status", "")
        source_refs = payload.get("sourceRefs", payload.get("source_refs", [test_id]))
        if isinstance(source_refs, str):
            source_refs = [source_refs]

        # Detect skip markers
        if status == "skipped" or payload.get("skip"):
            finding = _make_skip_finding(payload, framework, profile, source_refs, current_time, fixture_id)
            if finding:
                findings.append(finding)

        # Detect xfail markers
        if payload.get("xfail"):
            finding = _make_xfail_finding(payload, framework, profile, source_refs, current_time, fixture_id)
            if finding:
                findings.append(finding)

        # Detect only/focus markers (hard DQ in release/product)
        if payload.get("only"):
            finding = _make_only_finding(payload, framework, profile, source_refs, fixture_id)
            if finding:
                findings.append(finding)

        # Detect todo markers
        if payload.get("todo"):
            finding = _make_todo_finding(payload, framework, profile, source_refs, current_time, fixture_id)
            if finding:
                findings.append(finding)

        # Anti-evasion: scan message and other text fields for hidden markers
        anti_evasion = _detect_anti_evasion(payload, framework, test_id, source_refs)
        anti_evasion_matches.extend(anti_evasion)

        # Anti-evasion findings generate integrity signals
        for match in anti_evasion:
            if match.pattern.endswith("_only") or match.pattern.endswith("_focus"):
                finding = _make_only_finding_from_evasion(match, profile, fixture_id)
                findings.append(finding)
            elif match.pattern.endswith("_skip"):
                finding = _make_skip_finding_from_evasion(match, payload, profile, source_refs, current_time, fixture_id)
                if finding:
                    findings.append(finding)
            elif match.pattern.endswith("_todo"):
                finding = _make_todo_finding_from_evasion(match, profile, source_refs, current_time, fixture_id)
                if finding:
                    findings.append(finding)

    return findings, anti_evasion_matches


def build_test_integrity_report(
    test_records: list[dict[str, Any]],
    *,
    profile: str = "default",
    now: str | None = None,
    fixture_id: str = "test-integrity-skip-focus",
) -> dict[str, Any]:
    """Build complete test integrity report.

    Args:
        test_records: List of test_result records (normalized)
        profile: Profile for severity/effect calculation
        now: ISO timestamp
        fixture_id: Report identifier

    Returns:
        Dict with schema_version, record_type, findings, risk_debt, summary, sourceRefs
    """
    current_time = now or datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    findings, anti_evasion_matches = detect_test_integrity_signals(
        test_records,
        profile=profile,
        now=current_time,
        fixture_id=fixture_id,
    )

    # Generate risk debt for ALL non-pass findings (including soft_gap for visibility)
    risk_debt = _generate_risk_debt(findings, profile, current_time)

    # Aggregate source refs
    all_refs = set()
    for f in findings:
        all_refs.add(f.sourceRef)
    for d in risk_debt:
        all_refs.update(d.source_refs)
    for m in anti_evasion_matches:
        all_refs.add(m.source_ref)

    # Calculate summary
    summary = _build_summary(findings, risk_debt, profile)

    return {
        "schema_version": "HATE/v1",
        "record_type": "test_integrity_report",
        "fixture_id": fixture_id,
        "profile": profile,
        "summary": summary,
        "findings": [f.as_dict() for f in sorted(findings, key=lambda x: (x.severity, x.marker_kind))],
        "risk_debt": [d.as_dict() for d in sorted(risk_debt, key=lambda x: (x.severity, x.debt_id))],
        "anti_evasion": [m.as_dict() for m in anti_evasion_matches],
        "sourceRefs": sorted(all_refs),
    }


def _make_finding_id(fixture_id: str, marker_kind: str, test_id: str) -> str:
    """Generate unique finding ID."""
    return f"{fixture_id}.{marker_kind}.{test_id}"


def _make_skip_finding(
    payload: dict[str, Any],
    framework: str,
    profile: str,
    source_refs: list[str],
    now: str,
    fixture_id: str,
) -> IntegrityFinding | None:
    """Create finding for skip marker detection."""
    test_id = payload.get("canonical_test_id", "")
    has_reason = payload.get("skip_reason") or payload.get("message")
    has_owner = payload.get("skip_owner") or payload.get("owner")
    expiry = payload.get("skip_expiry") or payload.get("expiry_date")

    # Per packet spec: skip-without-reason is negative fixture
    # Per spec: skip in critical risk area => blocked in release/product
    severity_config = SIGNAL_SEVERITY_MATRIX[IntegritySignalType.SKIP_DETECTED].get(
        profile, SIGNAL_SEVERITY_MATRIX[IntegritySignalType.SKIP_DETECTED]["default"]
    )
    severity = severity_config["severity"]
    effect = severity_config["effect"]

    # Check for risk area context (from requirement_refs or risk_refs)
    risk_refs = payload.get("risk_refs", [])
    requirement_refs = payload.get("requirement_refs", [])
    is_critical_area = any(
        ref.lower().startswith("risk:critical") or "critical" in ref.lower()
        for ref in risk_refs + requirement_refs
    )

    if is_critical_area and profile in ("release", "product"):
        severity = "critical"
        effect = "blocked"

    # Build reason message
    reason_parts = []
    if not has_reason:
        reason_parts.append("skip marker without reason")
    if not has_owner:
        reason_parts.append("skip marker without owner assignment")

    reason = f"Test {test_id} has {', '.join(reason_parts) or 'skip marker'}"
    suggested_action = "Add skip reason and owner, or remove skip marker and run test"

    source_ref = source_refs[0] if source_refs else test_id

    return IntegrityFinding(
        finding_id=_make_finding_id(fixture_id, "skip", test_id),
        detector_id=DETECTOR_ID_SKIP_FOCUS,
        severity=severity,
        profile=profile,
        affected_test_id=test_id,
        marker_kind="skip",
        reason=reason,
        owner=has_owner,
        expiry=expiry,
        sourceRef=source_ref,
        readiness_effect=effect,
        suggested_manual_review_action=suggested_action,
    )


def _make_xfail_finding(
    payload: dict[str, Any],
    framework: str,
    profile: str,
    source_refs: list[str],
    now: str,
    fixture_id: str,
) -> IntegrityFinding | None:
    """Create finding for xfail marker detection."""
    test_id = payload.get("canonical_test_id", "")
    has_issue_ref = payload.get("xfail_issue") or payload.get("issue_ref")
    has_expiry = payload.get("xfail_expiry") or payload.get("expiry_date")
    has_owner = payload.get("xfail_owner") or payload.get("owner")

    # Per packet spec: xfail-without-expiry is negative fixture
    severity_config = SIGNAL_SEVERITY_MATRIX[IntegritySignalType.XFAIL_DETECTED].get(
        profile, SIGNAL_SEVERITY_MATRIX[IntegritySignalType.XFAIL_DETECTED]["default"]
    )
    severity = severity_config["severity"]
    effect = severity_config["effect"]

    # Missing issue ref or expiry escalates severity
    reason_parts = []
    if not has_issue_ref:
        reason_parts.append("xfail marker without issue reference")
        if profile in ("release", "product"):
            severity = "high"
            effect = "hold"
    if not has_expiry:
        reason_parts.append("xfail marker without expiry date")
        if profile in ("release", "product"):
            severity = "high"
            effect = "hold"

    reason = f"Test {test_id} has {', '.join(reason_parts) or 'xfail marker'}"
    suggested_action = "Add issue reference and expiry date, or remove xfail and fix underlying issue"

    source_ref = source_refs[0] if source_refs else test_id

    return IntegrityFinding(
        finding_id=_make_finding_id(fixture_id, "xfail", test_id),
        detector_id=DETECTOR_ID_SKIP_FOCUS,
        severity=severity,
        profile=profile,
        affected_test_id=test_id,
        marker_kind="xfail",
        reason=reason,
        owner=has_owner,
        expiry=has_expiry,
        sourceRef=source_ref,
        readiness_effect=effect,
        suggested_manual_review_action=suggested_action,
    )


def _make_only_finding(
    payload: dict[str, Any],
    framework: str,
    profile: str,
    source_refs: list[str],
    fixture_id: str,
) -> IntegrityFinding:
    """Create finding for only/focus marker detection."""
    test_id = payload.get("canonical_test_id", "")

    # Per packet spec: only-focused-leak is negative fixture
    # Per spec: `only` => hard_dq in release/product
    severity_config = SIGNAL_SEVERITY_MATRIX[IntegritySignalType.ONLY_DETECTED].get(
        profile, SIGNAL_SEVERITY_MATRIX[IntegritySignalType.ONLY_DETECTED]["default"]
    )
    severity = severity_config["severity"]
    effect = severity_config["effect"]

    reason = f"Test {test_id} has only/focus marker which may leak focused execution to CI"
    suggested_action = "Remove only/focus marker before commit"

    source_ref = source_refs[0] if source_refs else test_id

    return IntegrityFinding(
        finding_id=_make_finding_id(fixture_id, "only", test_id),
        detector_id=DETECTOR_ID_SKIP_FOCUS,
        severity=severity,
        profile=profile,
        affected_test_id=test_id,
        marker_kind="only",
        reason=reason,
        owner=None,
        expiry=None,
        sourceRef=source_ref,
        readiness_effect=effect,
        suggested_manual_review_action=suggested_action,
    )


def _make_todo_finding(
    payload: dict[str, Any],
    framework: str,
    profile: str,
    source_refs: list[str],
    now: str,
    fixture_id: str,
) -> IntegrityFinding | None:
    """Create finding for todo marker detection."""
    test_id = payload.get("canonical_test_id", "")

    # Per packet spec: todo-in-release-profile is negative fixture
    severity_config = SIGNAL_SEVERITY_MATRIX[IntegritySignalType.TODO_DETECTED].get(
        profile, SIGNAL_SEVERITY_MATRIX[IntegritySignalType.TODO_DETECTED]["default"]
    )
    severity = severity_config["severity"]
    effect = severity_config["effect"]

    # Per No-Go: todo in release profile => blocked (not warning)
    if profile == "release":
        severity = "high"
        effect = "blocked"

    # Per positive fixture: todo-non-release-profile is acceptable (soft_gap)
    reason = f"Test {test_id} has todo marker indicating incomplete test implementation"
    suggested_action = "Implement test or remove todo marker"

    # Non-release profile: soft_gap is acceptable
    if profile not in ("release", "product"):
        effect = "soft_gap"

    source_ref = source_refs[0] if source_refs else test_id

    return IntegrityFinding(
        finding_id=_make_finding_id(fixture_id, "todo", test_id),
        detector_id=DETECTOR_ID_SKIP_FOCUS,
        severity=severity,
        profile=profile,
        affected_test_id=test_id,
        marker_kind="todo",
        reason=reason,
        owner=None,
        expiry=None,
        sourceRef=source_ref,
        readiness_effect=effect,
        suggested_manual_review_action=suggested_action,
    )


def _detect_anti_evasion(
    payload: dict[str, Any],
    framework: str,
    test_id: str,
    source_refs: list[str],
) -> list[AntiEvasionMatch]:
    """Detect anti-evasion patterns in test content.

    Scans message, system-out, and other text fields for framework-specific
    hidden markers that bypass explicit flag detection.
    """
    matches: list[AntiEvasionMatch] = []
    patterns_for_framework = ANTI_EVASION_PATTERNS.get(framework, [])

    # Collect all text content to scan
    text_fields = [
        payload.get("message", ""),
        payload.get("system_out", ""),
        payload.get("system_err", ""),
        payload.get("failure_text", ""),
        payload.get("name", ""),
        payload.get("file", ""),
    ]
    text_blob = " ".join(field for field in text_fields if field)

    for pattern_re, pattern_name in patterns_for_framework:
        if re.search(pattern_re, text_blob):
            source_ref = source_refs[0] if source_refs else test_id
            matches.append(
                AntiEvasionMatch(
                    pattern=pattern_name,
                    test_id=test_id,
                    framework=framework,
                    source_ref=source_ref,
                )
            )

    return matches


def _make_only_finding_from_evasion(
    match: AntiEvasionMatch,
    profile: str,
    fixture_id: str,
) -> IntegrityFinding:
    """Create finding from anti-evasion only/focus detection."""
    severity_config = SIGNAL_SEVERITY_MATRIX[IntegritySignalType.ONLY_DETECTED].get(
        profile, SIGNAL_SEVERITY_MATRIX[IntegritySignalType.ONLY_DETECTED]["default"]
    )

    return IntegrityFinding(
        finding_id=_make_finding_id(fixture_id, "only", match.test_id),
        detector_id=DETECTOR_ID_SKIP_FOCUS,
        severity=severity_config["severity"],
        profile=profile,
        affected_test_id=match.test_id,
        marker_kind="only",
        reason=f"Anti-evasion: {match.framework} test {match.test_id} has hidden focus pattern {match.pattern}",
        owner=None,
        expiry=None,
        sourceRef=match.source_ref,
        readiness_effect=severity_config["effect"],
        suggested_manual_review_action="Remove focus/only wrapper before commit",
    )


def _make_skip_finding_from_evasion(
    match: AntiEvasionMatch,
    payload: dict[str, Any],
    profile: str,
    source_refs: list[str],
    now: str,
    fixture_id: str,
) -> IntegrityFinding | None:
    """Create finding from anti-evasion skip detection."""
    severity_config = SIGNAL_SEVERITY_MATRIX[IntegritySignalType.SKIP_DETECTED].get(
        profile, SIGNAL_SEVERITY_MATRIX[IntegritySignalType.SKIP_DETECTED]["default"]
    )

    return IntegrityFinding(
        finding_id=_make_finding_id(fixture_id, "skip", match.test_id),
        detector_id=DETECTOR_ID_SKIP_FOCUS,
        severity=severity_config["severity"],
        profile=profile,
        affected_test_id=match.test_id,
        marker_kind="skip",
        reason=f"Anti-evasion: {match.framework} test {match.test_id} has hidden skip pattern {match.pattern}",
        owner=None,
        expiry=None,
        sourceRef=match.source_ref,
        readiness_effect=severity_config["effect"],
        suggested_manual_review_action="Remove skip decorator or add justification",
    )


def _make_todo_finding_from_evasion(
    match: AntiEvasionMatch,
    profile: str,
    source_refs: list[str],
    now: str,
    fixture_id: str,
) -> IntegrityFinding | None:
    """Create finding from anti-evasion todo detection."""
    severity_config = SIGNAL_SEVERITY_MATRIX[IntegritySignalType.TODO_DETECTED].get(
        profile, SIGNAL_SEVERITY_MATRIX[IntegritySignalType.TODO_DETECTED]["default"]
    )

    return IntegrityFinding(
        finding_id=_make_finding_id(fixture_id, "todo", match.test_id),
        detector_id=DETECTOR_ID_SKIP_FOCUS,
        severity=severity_config["severity"],
        profile=profile,
        affected_test_id=match.test_id,
        marker_kind="todo",
        reason=f"Anti-evasion: {match.framework} test {match.test_id} has hidden todo pattern {match.pattern}",
        owner=None,
        expiry=None,
        sourceRef=match.source_ref,
        readiness_effect=severity_config["effect"],
        suggested_manual_review_action="Implement test or remove todo decorator",
    )


def _generate_risk_debt(
    findings: list[IntegrityFinding],
    profile: str,
    now: str,
) -> list[IntegrityRiskDebt]:
    """Generate risk debt entries for non-clean accepted/hold cases.

    Per packet spec: non-clean accepted/hold cases MUST generate risk debt.
    Also generates visible debt for accepted skip/xfail/todo (soft_gap cases).
    """
    debt: list[IntegrityRiskDebt] = []

    for finding in findings:
        # Generate debt for all non-pass findings to ensure visibility
        # Even accepted skip/xfail/todo (soft_gap) should have visible debt
        if finding.readiness_effect == "pass":
            continue

        test_id = finding.affected_test_id
        marker = finding.marker_kind

        debt_type = f"integrity_{marker}"

        # Determine blocking profile list based on readiness effect
        blocking_profile = []
        if finding.readiness_effect == "blocked":
            blocking_profile = ["release", "product"]
        elif finding.readiness_effect == "hold":
            blocking_profile = ["release"]
        elif finding.readiness_effect == "soft_gap":
            # Accepted debt still visible for soft_gap (not blocking any profile)
            blocking_profile = []

        # Determine debt status based on readiness effect
        # Accepted skip/xfail/todo with owner/reason are "accepted" status
        if finding.readiness_effect == "soft_gap" and finding.owner:
            status = "accepted"
        elif finding.readiness_effect == "soft_gap":
            status = "open"
        else:
            status = "open"

        debt_entry = IntegrityRiskDebt(
            debt_id=f"debt_{marker}_{test_id}",
            debt_type=debt_type,
            severity=finding.severity,
            status=status,
            test_id=test_id,
            marker=marker,
            owner=finding.owner,
            created_at=now,
            last_seen_at=now,
            age_days=0,
            source_refs=[finding.sourceRef],
            recommended_actions=[finding.suggested_manual_review_action],
            blocking_profile=blocking_profile,
            justification=finding.reason if finding.owner else None,
            expiry_date=finding.expiry,
        )
        debt.append(debt_entry)

    return debt


def _build_summary(
    findings: list[IntegrityFinding],
    risk_debt: list[IntegrityRiskDebt],
    profile: str,
) -> dict[str, Any]:
    """Build summary section of the report."""
    # Count by effect
    blocked_count = sum(1 for f in findings if f.readiness_effect == "blocked")
    hold_count = sum(1 for f in findings if f.readiness_effect == "hold")
    soft_gap_count = sum(1 for f in findings if f.readiness_effect == "soft_gap")
    pass_count = sum(1 for f in findings if f.readiness_effect == "pass")

    # Count by marker kind (signal type)
    skip_count = sum(1 for f in findings if f.marker_kind == "skip")
    xfail_count = sum(1 for f in findings if f.marker_kind == "xfail")
    only_count = sum(1 for f in findings if f.marker_kind == "only")
    todo_count = sum(1 for f in findings if f.marker_kind == "todo")

    # Overall status
    if blocked_count > 0:
        overall_status = "blocked"
    elif hold_count > 0:
        overall_status = "hold"
    elif soft_gap_count > 0:
        overall_status = "soft_gap"
    else:
        overall_status = "pass"

    return {
        "overall_status": overall_status,
        "finding_count": len(findings),
        "blocked_count": blocked_count,
        "hold_count": hold_count,
        "soft_gap_count": soft_gap_count,
        "pass_count": pass_count,
        "debt_count": len(risk_debt),
        "open_debt_count": sum(1 for d in risk_debt if d.status == "open"),
        "by_signal_type": {
            "skip": skip_count,
            "xfail": xfail_count,
            "only": only_count,
            "todo": todo_count,
        },
        "profile_effect": profile,
    }