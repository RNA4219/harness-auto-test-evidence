"""Test quality evaluation for HATE-GAP-054."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TestQualityFinding:
    code: str
    severity: str
    message: str
    sourceRef: str
    readiness_effect: str = "hold"

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "sourceRef": self.sourceRef,
            "readiness_effect": self.readiness_effect,
        }


def evaluate_test_quality_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_test_quality_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "test-quality-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_test_quality_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "test-quality-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["test-quality"])
    quality_config = _normalize_quality_config(input_data.get("quality_config", input_data))
    findings = _findings_for(quality_config, source_refs[0])
    status = "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": "test-quality-report",
        "report_id": report_id,
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "quality_config": quality_config,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "test_pattern_count": len(quality_config["test_patterns"]),
            "anti_pattern_count": len(quality_config["anti_patterns"]),
            "quality_metric_count": len(quality_config["quality_metrics"]),
            "confidence": quality_config["confidence"],
            "finding_count": len(findings),
        },
        "analysis_scope": quality_config["analysis_scope"],
        "input_refs": quality_config["input_refs"],
        "confidence": quality_config["confidence"],
        "limits": quality_config["limits"],
        "sourceRefs": sorted(set(source_refs)),
    }


def _normalize_quality_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw_config or {})
    test_patterns = [
        _normalize_test_pattern(tp)
        for tp in config.get("test_patterns", [])
        if isinstance(tp, dict)
    ]
    anti_patterns = [
        _normalize_anti_pattern(ap)
        for ap in config.get("anti_patterns", [])
        if isinstance(ap, dict)
    ]
    quality_metrics = [
        _normalize_quality_metric(qm)
        for qm in config.get("quality_metrics", [])
        if isinstance(qm, dict)
    ]
    return {
        "test_patterns": test_patterns,
        "anti_patterns": anti_patterns,
        "quality_metrics": quality_metrics,
        "analysis_scope": str(config.get("analysis_scope", "") or ""),
        "input_refs": [str(ref) for ref in config.get("input_refs", []) if str(ref)],
        "confidence": float(config.get("confidence", 0.0) or 0.0),
        "limits": _normalize_limits(config.get("limits", {})),
        "determinism_available": bool(config.get("determinism_available", True)),
        "timeout_available": bool(config.get("timeout_available", True)),
        "isolation_available": bool(config.get("isolation_available", True)),
    }


def _normalize_test_pattern(tp: dict[str, Any]) -> dict[str, Any]:
    return {
        "pattern_id": str(tp.get("pattern_id", "") or ""),
        "pattern_type": str(tp.get("pattern_type", "") or ""),
        "quality_dimension": str(tp.get("quality_dimension", "") or ""),
        "confidence": float(tp.get("confidence", 0.0) or 0.0),
        "sourceRef": str(tp.get("sourceRef", "") or ""),
        "rationale": str(tp.get("rationale", "") or ""),
        "verified": bool(tp.get("verified", True)),
    }


def _normalize_anti_pattern(ap: dict[str, Any]) -> dict[str, Any]:
    return {
        "anti_pattern_id": str(ap.get("anti_pattern_id", "") or ""),
        "anti_pattern_type": str(ap.get("anti_pattern_type", "") or ""),
        "severity": str(ap.get("severity", "") or ""),
        "confidence": float(ap.get("confidence", 0.0) or 0.0),
        "sourceRef": str(ap.get("sourceRef", "") or ""),
        "rationale": str(ap.get("rationale", "") or ""),
        "mitigated": bool(ap.get("mitigated", False)),
    }


def _normalize_quality_metric(qm: dict[str, Any]) -> dict[str, Any]:
    return {
        "metric_id": str(qm.get("metric_id", "") or ""),
        "metric_type": str(qm.get("metric_type", "") or ""),
        "value": float(qm.get("value", 0.0) or 0.0),
        "confidence": float(qm.get("confidence", 0.0) or 0.0),
        "sourceRef": str(qm.get("sourceRef", "") or ""),
        "rationale": str(qm.get("rationale", "") or ""),
    }


def _normalize_limits(limits: dict[str, Any]) -> dict[str, Any]:
    return {
        "max_test_patterns": int(limits.get("max_test_patterns", 100) or 100),
        "max_anti_patterns": int(limits.get("max_anti_patterns", 100) or 100),
        "max_quality_metrics": int(limits.get("max_quality_metrics", 100) or 100),
        "confidence_threshold": float(limits.get("confidence_threshold", 0.7) or 0.7),
    }


def _findings_for(config: dict[str, Any], source_ref: str) -> list[TestQualityFinding]:
    findings: list[TestQualityFinding] = []

    # HATE-GAP-054 primary negative: sleep-based-test-hold
    sleep_anti_patterns = [ap for ap in config["anti_patterns"] if ap.get("anti_pattern_type") == "sleep_based" and not ap.get("mitigated")]

    if sleep_anti_patterns:
        findings.append(_finding(
            "test_quality_sleep_based_test_hold",
            "Sleep-based test anti-pattern detected.",
            source_ref,
        ))

    # Additional finding codes from vocabulary
    if not config["determinism_available"]:
        findings.append(_finding(
            "test_quality_determinism_missing",
            "Test quality requires determinism verification.",
            source_ref,
        ))

    if not config["timeout_available"]:
        findings.append(_finding(
            "test_quality_timeout_missing",
            "Test quality requires timeout verification.",
            source_ref,
        ))

    if not config["isolation_available"]:
        findings.append(_finding(
            "test_quality_isolation_missing",
            "Test quality requires isolation verification.",
            source_ref,
        ))

    for ap in config["anti_patterns"]:
        if ap.get("severity") == "critical" and not ap.get("mitigated"):
            findings.append(_finding(
                "test_quality_sleep_based_test_hold",
                f"Anti-pattern '{ap.get('anti_pattern_id')}' with critical severity not mitigated.",
                source_ref,
            ))

    for tp in config["test_patterns"]:
        if not tp.get("sourceRef"):
            findings.append(_finding(
                "test_quality_determinism_missing",
                f"Test pattern '{tp.get('pattern_id')}' missing sourceRef.",
                source_ref,
            ))

    for ap in config["anti_patterns"]:
        if not ap.get("sourceRef"):
            findings.append(_finding(
                "test_quality_sleep_based_test_hold",
                f"Anti-pattern '{ap.get('anti_pattern_id')}' missing sourceRef.",
                source_ref,
            ))

    if config["confidence"] < config["limits"]["confidence_threshold"]:
        findings.append(_finding(
            "test_quality_sleep_based_test_hold",
            f"Test quality confidence {config['confidence']} below threshold {config['limits']['confidence_threshold']}.",
            source_ref,
        ))

    return findings


def _finding(code: str, message: str, source_ref: str) -> TestQualityFinding:
    return TestQualityFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
    )