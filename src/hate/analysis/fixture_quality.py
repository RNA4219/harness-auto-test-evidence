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
    diagnostics = _derive_diagnostics(config)
    findings = _findings_for(config, diagnostics, source_refs[0])
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
            "duplicate_fixture_id_count": len(diagnostics["duplicate_fixture_ids"]),
            "weak_negative_count": len(diagnostics["weak_negative_fixture_ids"]),
            "expected_leakage_count": len(diagnostics["expected_leakage_fixture_ids"]),
            "missing_positive_count": len(diagnostics["missing_fixture_types"]["positive"]),
            "missing_negative_count": len(diagnostics["missing_fixture_types"]["negative"]),
            "confidence": config["confidence"],
            "finding_count": len(findings),
        },
        "fixture_findings": config["fixture_findings"],
        "corpus_scope": config["corpus_scope"],
        "schema_drift": config["schema_drift"],
        "fixture_quality_diagnostics": diagnostics,
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
        "expected": dict(f.get("expected", {}) or {}),
        "input": dict(f.get("input", {}) or {}),
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
        "min_positive_fixtures": int(limits.get("min_positive_fixtures", 1) or 1),
        "min_negative_fixtures": int(limits.get("min_negative_fixtures", 1) or 1),
    }


def _derive_diagnostics(config: dict[str, Any]) -> dict[str, Any]:
    fixture_findings = config["fixture_findings"]
    fixture_ids = [f["fixture_id"] for f in fixture_findings if f["fixture_id"]]
    seen: set[str] = set()
    duplicates: list[str] = []
    for fixture_id in fixture_ids:
        if fixture_id in seen and fixture_id not in duplicates:
            duplicates.append(fixture_id)
        seen.add(fixture_id)

    by_type = {"positive": [], "negative": []}
    for f in fixture_findings:
        if f["fixture_type"] in by_type:
            by_type[f["fixture_type"]].append(f["fixture_id"])

    weak_negative_ids = sorted({
        f["fixture_id"]
        for f in fixture_findings
        if f["fixture_type"] == "negative" and _is_weak_negative(f)
    })
    expected_leakage_ids = sorted({
        f["fixture_id"]
        for f in fixture_findings
        if _has_expected_leakage(f)
    })
    missing_types = {
        "positive": [] if len(by_type["positive"]) >= config["limits"]["min_positive_fixtures"] else ["positive"],
        "negative": [] if len(by_type["negative"]) >= config["limits"]["min_negative_fixtures"] else ["negative"],
    }
    return {
        "duplicate_fixture_ids": sorted(duplicates),
        "weak_negative_fixture_ids": weak_negative_ids,
        "expected_leakage_fixture_ids": expected_leakage_ids,
        "fixture_type_counts": {key: len(value) for key, value in by_type.items()},
        "missing_fixture_types": missing_types,
    }


def _is_weak_negative(finding: dict[str, Any]) -> bool:
    metrics = finding["quality_metrics"]
    expected = finding["expected"]
    rationale = finding["rationale"].lower()
    if expected.get("status") in {"hold", "blocked"} or expected.get("readiness_effect") in {"hold", "blocked"}:
        return False
    if metrics.get("asserts_finding_code") is True or metrics.get("negative_oracle") is True:
        return False
    return "negative" in rationale and "finding" not in rationale and "hold" not in rationale


def _has_expected_leakage(finding: dict[str, Any]) -> bool:
    combined = {
        "input": finding["input"],
        "quality_metrics": finding["quality_metrics"],
    }
    leakage_terms = ("expected", "golden", "fixture_name", "case_name", "expected_status", "expected_code")
    return _contains_leakage_term(combined, leakage_terms)


def _contains_leakage_term(value: Any, terms: tuple[str, ...]) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            key_lower = str(key).lower()
            if any(term in key_lower for term in terms):
                return True
            if _contains_leakage_term(child, terms):
                return True
    elif isinstance(value, list):
        return any(_contains_leakage_term(child, terms) for child in value)
    elif isinstance(value, str):
        lower = value.lower()
        return any(term in lower for term in terms)
    return False


def _findings_for(
    config: dict[str, Any],
    diagnostics: dict[str, Any],
    source_ref: str,
) -> list[FixtureQualityFinding]:
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

    if diagnostics["expected_leakage_fixture_ids"]:
        findings.append(_finding(
            "fixture_quality_expected_output_leakage",
            f"Expected output leakage indicators found in fixtures: {', '.join(diagnostics['expected_leakage_fixture_ids'])}.",
            source_ref,
        ))

    if diagnostics["duplicate_fixture_ids"]:
        findings.append(_finding(
            "fixture_quality_duplicate_fixture_id",
            f"Duplicate fixture ids detected: {', '.join(diagnostics['duplicate_fixture_ids'])}.",
            source_ref,
        ))

    if len(config["fixture_findings"]) > config["limits"]["max_fixture_findings"]:
        findings.append(_finding(
            "fixture_quality_finding_budget_exceeded",
            f"Fixture finding count {len(config['fixture_findings'])} exceeds limit {config['limits']['max_fixture_findings']}.",
            source_ref,
        ))

    if diagnostics["weak_negative_fixture_ids"]:
        findings.append(_finding(
            "fixture_quality_weak_negative_oracle",
            f"Negative fixtures lack explicit hold/block oracle: {', '.join(diagnostics['weak_negative_fixture_ids'])}.",
            source_ref,
        ))

    missing_types = diagnostics["missing_fixture_types"]
    if missing_types["positive"] or missing_types["negative"]:
        missing = sorted(missing_types["positive"] + missing_types["negative"])
        findings.append(_finding(
            "fixture_quality_fixture_matrix_incomplete",
            f"Fixture matrix missing required fixture types: {', '.join(missing)}.",
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
