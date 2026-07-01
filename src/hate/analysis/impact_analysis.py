"""Impact analysis evaluation for HATE-GAP-049."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ImpactAnalysisFinding:
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


def evaluate_impact_analysis_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_impact_analysis_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "impact-analysis-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_impact_analysis_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "impact-analysis-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["impact-analysis"])
    impact_config = _normalize_impact_config(input_data.get("impact_config", input_data))
    findings = _findings_for(impact_config, source_refs[0])
    status = "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": "impact-analysis-report",
        "report_id": report_id,
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "impact_config": impact_config,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "changed_ref_count": len(impact_config["changed_refs"]),
            "affected_test_count": len(impact_config["affected_tests"]),
            "affected_requirement_count": len(impact_config["affected_requirements"]),
            "confidence": impact_config["confidence"],
            "finding_count": len(findings),
        },
        "analysis_scope": impact_config["analysis_scope"],
        "input_refs": impact_config["input_refs"],
        "confidence": impact_config["confidence"],
        "limits": impact_config["limits"],
        "sourceRefs": sorted(set(source_refs)),
    }


def _normalize_impact_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw_config or {})
    changed_refs = [
        _normalize_changed_ref(ref)
        for ref in config.get("changed_refs", [])
        if isinstance(ref, dict)
    ]
    affected_tests = [
        _normalize_affected_test(test)
        for test in config.get("affected_tests", [])
        if isinstance(test, dict)
    ]
    affected_requirements = [
        _normalize_affected_requirement(req)
        for req in config.get("affected_requirements", [])
        if isinstance(req, dict)
    ]
    return {
        "changed_refs": changed_refs,
        "affected_tests": affected_tests,
        "affected_requirements": affected_requirements,
        "analysis_scope": str(config.get("analysis_scope", "") or ""),
        "input_refs": [str(ref) for ref in config.get("input_refs", []) if str(ref)],
        "confidence": float(config.get("confidence", 0.0) or 0.0),
        "limits": _normalize_limits(config.get("limits", {})),
        "dependency_sources_available": bool(config.get("dependency_sources_available", False)),
        "ownership_sources_available": bool(config.get("ownership_sources_available", False)),
        "history_sources_available": bool(config.get("history_sources_available", False)),
    }


def _normalize_changed_ref(ref: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": str(ref.get("path", "") or ""),
        "change_type": str(ref.get("change_type", "") or ""),
        "sourceRef": str(ref.get("sourceRef", "") or ""),
    }


def _normalize_affected_test(test: dict[str, Any]) -> dict[str, Any]:
    return {
        "test_id": str(test.get("test_id", "") or ""),
        "confidence": float(test.get("confidence", 0.0) or 0.0),
        "sourceRef": str(test.get("sourceRef", "") or ""),
        "rationale": str(test.get("rationale", "") or ""),
    }


def _normalize_affected_requirement(req: dict[str, Any]) -> dict[str, Any]:
    return {
        "requirement_id": str(req.get("requirement_id", "") or ""),
        "confidence": float(req.get("confidence", 0.0) or 0.0),
        "sourceRef": str(req.get("sourceRef", "") or ""),
        "rationale": str(req.get("rationale", "") or ""),
    }


def _normalize_limits(limits: dict[str, Any]) -> dict[str, Any]:
    return {
        "max_affected_tests": int(limits.get("max_affected_tests", 1000) or 1000),
        "max_affected_requirements": int(limits.get("max_affected_requirements", 100) or 100),
        "confidence_threshold": float(limits.get("confidence_threshold", 0.7) or 0.7),
    }


def _findings_for(config: dict[str, Any], source_ref: str) -> list[ImpactAnalysisFinding]:
    findings: list[ImpactAnalysisFinding] = []

    # HATE-GAP-049 primary negative: missing dependency source
    if not config["dependency_sources_available"]:
        findings.append(_finding(
            "impact_analysis_missing_dependency_source",
            "Impact analysis requires dependency source data for inference.",
            source_ref,
        ))

    # Additional finding codes from vocabulary
    if config["confidence"] < config["limits"]["confidence_threshold"]:
        findings.append(_finding(
            "impact_analysis_confidence_missing",
            f"Impact analysis confidence {config['confidence']} below threshold {config['limits']['confidence_threshold']}.",
            source_ref,
        ))

    for test in config["affected_tests"]:
        if not test.get("sourceRef"):
            findings.append(_finding(
                "impact_analysis_affected_test_without_source_ref",
                f"Affected test '{test.get('test_id')}' missing sourceRef.",
                source_ref,
            ))

    for req in config["affected_requirements"]:
        if not req.get("sourceRef"):
            findings.append(_finding(
                "impact_analysis_affected_requirement_without_source_ref",
                f"Affected requirement '{req.get('requirement_id')}' missing sourceRef.",
                source_ref,
            ))

    if not config["ownership_sources_available"]:
        findings.append(_finding(
            "impact_analysis_missing_ownership_source",
            "Impact analysis requires ownership source data for inference.",
            source_ref,
        ))

    if not config["history_sources_available"]:
        findings.append(_finding(
            "impact_analysis_missing_history_source",
            "Impact analysis requires history source data for inference.",
            source_ref,
        ))

    return findings


def _finding(code: str, message: str, source_ref: str) -> ImpactAnalysisFinding:
    return ImpactAnalysisFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
    )
