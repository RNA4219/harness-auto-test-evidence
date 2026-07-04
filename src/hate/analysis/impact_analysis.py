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
    diagnostics = _derive_diagnostics(impact_config)
    findings = _findings_for(impact_config, diagnostics, source_refs[0])
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
            "derived_test_count": len(diagnostics["derived_affected_tests"]),
            "derived_requirement_count": len(diagnostics["derived_affected_requirements"]),
            "owner_count": len(diagnostics["owners"]),
            "unmapped_changed_ref_count": len(diagnostics["unmapped_changed_refs"]),
            "confidence": impact_config["confidence"],
            "finding_count": len(findings),
        },
        "derived_affected_tests": diagnostics["derived_affected_tests"],
        "derived_affected_requirements": diagnostics["derived_affected_requirements"],
        "impact_analysis_diagnostics": diagnostics,
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
        "dependency_graph": _normalize_mapping(config.get("dependency_graph", {})),
        "ownership_map": _normalize_mapping(config.get("ownership_map", {})),
        "history_index": _normalize_mapping(config.get("history_index", {})),
        "requirement_map": _normalize_mapping(config.get("requirement_map", {})),
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


def _normalize_mapping(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, list[str]] = {}
    for key, raw_values in value.items():
        if isinstance(raw_values, list):
            normalized[str(key)] = [str(v) for v in raw_values if str(v)]
        elif raw_values:
            normalized[str(key)] = [str(raw_values)]
    return normalized


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
        "max_changed_refs": int(limits.get("max_changed_refs", 500) or 500),
        "confidence_threshold": float(limits.get("confidence_threshold", 0.7) or 0.7),
    }


def _derive_diagnostics(config: dict[str, Any]) -> dict[str, Any]:
    changed_paths = [ref["path"] for ref in config["changed_refs"] if ref["path"]]
    derived_tests = _derive_from_maps(changed_paths, config["dependency_graph"], config["history_index"], prefix="test")
    derived_requirements = _derive_from_maps(changed_paths, config["requirement_map"], {}, prefix="requirement")
    owners = sorted({
        owner
        for path in changed_paths
        for owner in _lookup_path_values(path, config["ownership_map"])
    })
    explicit_tests = {test["test_id"] for test in config["affected_tests"] if test["test_id"]}
    explicit_requirements = {req["requirement_id"] for req in config["affected_requirements"] if req["requirement_id"]}
    unmapped = sorted(
        path
        for path in changed_paths
        if not _lookup_path_values(path, config["dependency_graph"])
        and not _lookup_path_values(path, config["history_index"])
        and not _lookup_path_values(path, config["requirement_map"])
    )
    return {
        "derived_affected_tests": [item for item in derived_tests if item["test_id"] not in explicit_tests],
        "derived_affected_requirements": [
            item for item in derived_requirements if item["requirement_id"] not in explicit_requirements
        ],
        "owners": owners,
        "unmapped_changed_refs": unmapped,
        "changed_refs_missing_source": sorted(ref["path"] for ref in config["changed_refs"] if ref["path"] and not ref["sourceRef"]),
    }


def _derive_from_maps(
    changed_paths: list[str],
    primary_map: dict[str, list[str]],
    secondary_map: dict[str, list[str]],
    *,
    prefix: str,
) -> list[dict[str, Any]]:
    derived: dict[str, dict[str, Any]] = {}
    for path in changed_paths:
        for value in _lookup_path_values(path, primary_map):
            key = "test_id" if prefix == "test" else "requirement_id"
            derived[value] = {
                key: value,
                "confidence": 0.85,
                "sourceRef": f"impact:{path}",
                "rationale": f"Matched {path} via dependency map.",
            }
        for value in _lookup_path_values(path, secondary_map):
            key = "test_id" if prefix == "test" else "requirement_id"
            derived.setdefault(value, {
                key: value,
                "confidence": 0.75,
                "sourceRef": f"impact:{path}",
                "rationale": f"Matched {path} via history index.",
            })
    return sorted(derived.values(), key=lambda item: item["test_id" if prefix == "test" else "requirement_id"])


def _lookup_path_values(path: str, mapping: dict[str, list[str]]) -> list[str]:
    values: list[str] = []
    for pattern, mapped in mapping.items():
        if path == pattern or path.startswith(pattern.rstrip("/") + "/") or pattern in path:
            values.extend(mapped)
    return sorted(set(values))


def _findings_for(
    config: dict[str, Any],
    diagnostics: dict[str, Any],
    source_ref: str,
) -> list[ImpactAnalysisFinding]:
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

    for path in diagnostics["changed_refs_missing_source"]:
        findings.append(_finding(
            "impact_analysis_changed_ref_without_source_ref",
            f"Changed ref '{path}' missing sourceRef.",
            source_ref,
        ))

    if diagnostics["unmapped_changed_refs"]:
        findings.append(_finding(
            "impact_analysis_unmapped_changed_ref",
            f"Changed refs have no derived impact mapping: {', '.join(diagnostics['unmapped_changed_refs'])}.",
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

    if len(config["changed_refs"]) > config["limits"]["max_changed_refs"]:
        findings.append(_finding(
            "impact_analysis_changed_ref_budget_exceeded",
            f"Changed ref count {len(config['changed_refs'])} exceeds limit {config['limits']['max_changed_refs']}.",
            source_ref,
        ))

    total_tests = len(config["affected_tests"]) + len(diagnostics["derived_affected_tests"])
    if total_tests > config["limits"]["max_affected_tests"]:
        findings.append(_finding(
            "impact_analysis_affected_test_budget_exceeded",
            f"Affected test count {total_tests} exceeds limit {config['limits']['max_affected_tests']}.",
            source_ref,
        ))

    total_requirements = len(config["affected_requirements"]) + len(diagnostics["derived_affected_requirements"])
    if total_requirements > config["limits"]["max_affected_requirements"]:
        findings.append(_finding(
            "impact_analysis_affected_requirement_budget_exceeded",
            f"Affected requirement count {total_requirements} exceeds limit {config['limits']['max_affected_requirements']}.",
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
