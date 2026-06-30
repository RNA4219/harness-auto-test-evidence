"""Fixture quality analysis for HATE-GAP-059."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FixtureQualityFinding:
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


def evaluate_fixture_quality_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_fixture_quality_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "fixture-quality-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_fixture_quality_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "fixture-quality-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["fixture-quality"])
    config = _normalize_fixture_quality_config(input_data.get("fixture_quality_config", input_data))
    findings = _findings_for(config, source_refs[0])
    status = "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": "fixture-quality-report",
        "report_id": report_id,
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "analysis_scope": config["analysis_scope"],
        "fixture_quality_config": config,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "fixture_finding_count": len(config["fixture_findings"]),
            "corpus_fixture_count": config["corpus_scope"]["fixture_count"],
            "schema_drift_detected": config["schema_drift"]["drift_detected"],
            "confidence": config["confidence"],
            "finding_count": len(findings),
        },
        "fixture_findings": config["fixture_findings"],
        "corpus_scope": config["corpus_scope"],
        "schema_drift": config["schema_drift"],
        "input_refs": config["input_refs"],
        "confidence": config["confidence"],
        "limits": config["limits"],
        "sourceRefs": sorted(set(source_refs)),
    }


def _normalize_fixture_quality_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw_config or {})
    fixture_findings = [
        _normalize_fixture_finding(f)
        for f in config.get("fixture_findings", [])
        if isinstance(f, dict)
    ]
    corpus_scope = _normalize_corpus_scope(config.get("corpus_scope", {}))
    schema_drift = _normalize_schema_drift(config.get("schema_drift", {}))
    return {
        "fixture_findings": fixture_findings,
        "corpus_scope": corpus_scope,
        "schema_drift": schema_drift,
        "analysis_scope": str(config.get("analysis_scope", "") or ""),
        "fixture_name_behavior_coupled": bool(config.get("fixture_name_behavior_coupled", False)),
        "expected_output_exposed": bool(config.get("expected_output_exposed", False)),
        "confidence": float(config.get("confidence", 0.0) or 0.0),
        "input_refs": [str(ref) for ref in config.get("input_refs", []) if str(ref)],
        "limits": _normalize_limits(config.get("limits", {})),
    }


def _normalize_fixture_finding(f: dict[str, Any]) -> dict[str, Any]:
    return {
        "fixture_id": str(f.get("fixture_id", "") or ""),
        "fixture_type": str(f.get("fixture_type", "") or ""),
        "quality_metrics": dict(f.get("quality_metrics", {}) or {}),
        "sourceRef": str(f.get("sourceRef", "") or ""),
        "rationale": str(f.get("rationale", "") or ""),
    }


def _normalize_corpus_scope(c: dict[str, Any]) -> dict[str, Any]:
    return {
        "corpus_id": str(c.get("corpus_id", "") or ""),
        "fixture_count": int(c.get("fixture_count", 0) or 0),
        "coverage_target": float(c.get("coverage_target", 0.0) or 0.0),
        "completeness_baseline": float(c.get("completeness_baseline", 0.0) or 0.0),
    }


def _normalize_schema_drift(s: dict[str, Any]) -> dict[str, Any]:
    return {
        "drift_detected": bool(s.get("drift_detected", False)),
        "schema_version": str(s.get("schema_version", "") or ""),
        "baseline_version": str(s.get("baseline_version", "") or ""),
        "drift_fields": list(s.get("drift_fields", []) or []),
    }


def _normalize_limits(limits: dict[str, Any]) -> dict[str, Any]:
    return {
        "confidence_threshold": float(limits.get("confidence_threshold", 0.7) or 0.7),
        "max_fixture_findings": int(limits.get("max_fixture_findings", 50) or 50),
        "coverage_threshold": float(limits.get("coverage_threshold", 0.8) or 0.8),
    }


def _findings_for(config: dict[str, Any], source_ref: str) -> list[FixtureQualityFinding]:
    findings: list[FixtureQualityFinding] = []

    # HATE-GAP-059 primary negative: fixture name behavior coupled
    if config.get("fixture_name_behavior_coupled"):
        findings.append(_finding(
            "fixture_quality_fixture_name_coupled_hold",
            "Fixture name behavior coupled detected.",
            source_ref,
        ))

    # Expected output exposed (禁止: expected_output leakage)
    if config.get("expected_output_exposed"):
        findings.append(_finding(
            "fixture_quality_expected_output_leakage",
            "Expected output exposed in fixture.",
            source_ref,
        ))

    # Schema drift detection
    if config["schema_drift"]["drift_detected"]:
        findings.append(_finding(
            "fixture_quality_schema_drift",
            "Schema version drift detected.",
            source_ref,
        ))

    # Check for missing sourceRef on fixture findings
    for f in config["fixture_findings"]:
        if not f.get("sourceRef"):
            findings.append(_finding(
                "fixture_quality_fixture_name_coupled_hold",
                f"Fixture finding '{f.get('fixture_id')}' missing sourceRef.",
                source_ref,
            ))

    # Coverage threshold check
    corpus_coverage = config["corpus_scope"]["coverage_target"]
    if corpus_coverage < config["limits"]["coverage_threshold"]:
        findings.append(_finding(
            "fixture_quality_fixture_name_coupled_hold",
            f"Corpus coverage {corpus_coverage} below threshold {config['limits']['coverage_threshold']}.",
            source_ref,
        ))

    # Confidence threshold check
    if config["confidence"] < config["limits"]["confidence_threshold"]:
        findings.append(_finding(
            "fixture_quality_fixture_name_coupled_hold",
            f"Fixture quality confidence {config['confidence']} below threshold {config['limits']['confidence_threshold']}.",
            source_ref,
        ))

    return findings


def _finding(code: str, message: str, source_ref: str) -> FixtureQualityFinding:
    return FixtureQualityFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
    )
