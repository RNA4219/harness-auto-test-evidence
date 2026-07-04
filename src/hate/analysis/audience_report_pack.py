"""Audience report pack analysis for HATE-GAP-058."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AudienceReportPackFinding:
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


def evaluate_audience_report_pack_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_audience_report_pack(
        input_data,
        report_id=str(payload.get("fixture_id") or "audience-report-pack-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_audience_report_pack(
    input_data: dict[str, Any],
    *,
    report_id: str = "audience-report-pack",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["audience-report-pack"])
    config = _normalize_audience_config(input_data.get("audience_config", input_data))
    diagnostics = _derive_diagnostics(config)
    findings = _findings_for(config, diagnostics, source_refs[0])
    status = "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": "audience-report-pack",
        "report_id": report_id,
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "analysis_scope": config["analysis_scope"],
        "audience_config": config,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "view_count": len(config["audience_views"]),
            "shared_sourceRef_count": len(config["shared_sourceRefs"]),
            "required_audience_count": len(config["required_audiences"]),
            "missing_audience_count": len(diagnostics["missing_audiences"]),
            "view_sourceRef_drift_count": len(diagnostics["view_sourceRef_drift"]),
            "verdict_drift_count": len(diagnostics["verdict_drift_views"]),
            "verdict_recomputed": config["verdict_recomputed"],
            "confidence": config["confidence"],
            "finding_count": len(findings),
        },
        "audience_pack_diagnostics": diagnostics,
        "audience_views": config["audience_views"],
        "shared_sourceRefs": config["shared_sourceRefs"],
        "verdict_recomputed": config["verdict_recomputed"],
        "input_refs": config["input_refs"],
        "confidence": config["confidence"],
        "limits": config["limits"],
        "sourceRefs": sorted(set(source_refs)),
    }


def _normalize_audience_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw_config or {})
    audience_views = [
        _normalize_audience_view(v)
        for v in config.get("audience_views", [])
        if isinstance(v, dict)
    ]
    shared_sourceRefs = [
        str(ref) for ref in config.get("shared_sourceRefs", [])
        if str(ref)
    ]
    required_audiences = [
        str(audience) for audience in config.get(
            "required_audiences",
            ["developer", "qa", "release", "qeg", "machine"],
        )
        if str(audience)
    ]
    return {
        "audience_views": audience_views,
        "shared_sourceRefs": shared_sourceRefs,
        "required_audiences": required_audiences,
        "base_verdict": str(config.get("base_verdict", "") or ""),
        "analysis_scope": str(config.get("analysis_scope", "") or ""),
        "verdict_recomputed": bool(config.get("verdict_recomputed", False)),
        "source_ref_drift_detected": bool(config.get("source_ref_drift_detected", False)),
        "confidence": float(config.get("confidence", 0.0) or 0.0),
        "input_refs": [str(ref) for ref in config.get("input_refs", []) if str(ref)],
        "limits": _normalize_limits(config.get("limits", {})),
    }


def _normalize_audience_view(v: dict[str, Any]) -> dict[str, Any]:
    source_refs = [str(ref) for ref in v.get("sourceRefs", []) if str(ref)]
    source_ref = str(v.get("sourceRef", "") or "")
    if source_ref and source_ref not in source_refs:
        source_refs.append(source_ref)
    return {
        "audience_id": str(v.get("audience_id", "") or ""),
        "view_type": str(v.get("view_type", "") or ""),
        "verdict": str(v.get("verdict", "") or ""),
        "sourceRef": source_ref,
        "sourceRefs": source_refs,
        "sections": [str(section) for section in v.get("sections", []) if str(section)],
        "machine_readable": bool(v.get("machine_readable", False)),
        "rationale": str(v.get("rationale", "") or ""),
    }


def _normalize_limits(limits: dict[str, Any]) -> dict[str, Any]:
    return {
        "confidence_threshold": float(limits.get("confidence_threshold", 0.7) or 0.7),
        "max_views": int(limits.get("max_views", 10) or 10),
        "max_sourceRefs": int(limits.get("max_sourceRefs", 50) or 50),
    }


def _derive_diagnostics(config: dict[str, Any]) -> dict[str, Any]:
    view_types = [view["view_type"] for view in config["audience_views"] if view["view_type"]]
    view_ids = [view["audience_id"] for view in config["audience_views"] if view["audience_id"]]
    shared_refs = set(config["shared_sourceRefs"])
    base_verdict = config["base_verdict"]
    verdicts = {view["verdict"] for view in config["audience_views"] if view["verdict"]}
    expected_verdict = base_verdict or (next(iter(verdicts)) if len(verdicts) == 1 else "")
    verdict_drift = [
        view["audience_id"] or view["view_type"]
        for view in config["audience_views"]
        if expected_verdict and view["verdict"] and view["verdict"] != expected_verdict
    ]
    if not expected_verdict and len(verdicts) > 1:
        verdict_drift = [
            view["audience_id"] or view["view_type"]
            for view in config["audience_views"]
            if view["verdict"]
        ]
    required_sections = {
        "developer": {"findings", "commands"},
        "qa": {"test_cases", "risks"},
        "release": {"decision", "open_risks"},
        "qeg": {"sourceRefs", "external_refs"},
        "machine": {"json", "schema_version"},
    }
    missing_sections: list[str] = []
    for view in config["audience_views"]:
        expected_sections = required_sections.get(view["view_type"], set())
        if expected_sections and not expected_sections.issubset(set(view["sections"])):
            missing_sections.append(view["audience_id"] or view["view_type"])
    return {
        "missing_audiences": sorted(set(config["required_audiences"]) - set(view_types)),
        "duplicate_audience_ids": sorted({item for item in view_ids if view_ids.count(item) > 1}),
        "duplicate_view_types": sorted({item for item in view_types if view_types.count(item) > 1}),
        "view_sourceRef_drift": sorted(
            view["audience_id"] or view["view_type"]
            for view in config["audience_views"]
            if any(ref not in shared_refs for ref in view["sourceRefs"])
        ),
        "verdict_drift_views": sorted(verdict_drift),
        "missing_required_sections": sorted(missing_sections),
        "machine_view_missing": "machine" in config["required_audiences"] and "machine" not in view_types,
        "machine_view_not_readable": any(
            view["view_type"] == "machine" and not view["machine_readable"]
            for view in config["audience_views"]
        ),
        "budget_exceeded": {
            "views": len(config["audience_views"]) > config["limits"]["max_views"],
            "sourceRefs": len(config["shared_sourceRefs"]) > config["limits"]["max_sourceRefs"],
        },
    }


def _findings_for(
    config: dict[str, Any],
    diagnostics: dict[str, Any],
    source_ref: str,
) -> list[AudienceReportPackFinding]:
    findings: list[AudienceReportPackFinding] = []

    # HATE-GAP-058 primary negative: verdict recomputed denied
    # 禁止: verdict再計算不可
    if config["verdict_recomputed"]:
        findings.append(_finding(
            "audience_report_pack_verdict_recomputed_denied",
            "Verdict recomputed - audience report must not recalculate verdict.",
            source_ref,
        ))

    # Source ref drift detection
    if config.get("source_ref_drift_detected"):
        findings.append(_finding(
            "audience_report_pack_source_ref_drift",
            "Source reference drift detected across audience views.",
            source_ref,
        ))

    if diagnostics["missing_audiences"]:
        findings.append(_finding(
            "audience_report_pack_view_missing",
            f"Required audience views missing: {', '.join(diagnostics['missing_audiences'])}.",
            source_ref,
        ))

    if diagnostics["duplicate_audience_ids"] or diagnostics["duplicate_view_types"]:
        findings.append(_finding(
            "audience_report_pack_duplicate_view",
            "Audience report pack contains duplicate audience ids or view types.",
            source_ref,
        ))

    if diagnostics["view_sourceRef_drift"]:
        findings.append(_finding(
            "audience_report_pack_source_ref_drift",
            f"Audience views reference non-shared sourceRefs: {', '.join(diagnostics['view_sourceRef_drift'])}.",
            source_ref,
        ))

    if diagnostics["verdict_drift_views"]:
        findings.append(_finding(
            "audience_report_pack_verdict_drift",
            f"Audience views diverge from the shared verdict: {', '.join(diagnostics['verdict_drift_views'])}.",
            source_ref,
        ))

    if diagnostics["missing_required_sections"]:
        findings.append(_finding(
            "audience_report_pack_view_missing",
            f"Audience views missing required sections: {', '.join(diagnostics['missing_required_sections'])}.",
            source_ref,
        ))

    if diagnostics["machine_view_missing"] or diagnostics["machine_view_not_readable"]:
        findings.append(_finding(
            "audience_report_pack_machine_view_invalid",
            "Machine audience view must exist and be machine readable.",
            source_ref,
        ))

    # Check for missing sourceRef on audience views
    for v in config["audience_views"]:
        if not v.get("sourceRef"):
            findings.append(_finding(
                "audience_report_pack_view_missing",
                f"Audience view '{v.get('audience_id')}' missing sourceRef.",
                source_ref,
            ))
        if not v.get("verdict"):
            findings.append(_finding(
                "audience_report_pack_view_missing",
                f"Audience view '{v.get('audience_id')}' missing verdict.",
                source_ref,
            ))

    # Empty shared sourceRefs check
    if not config["shared_sourceRefs"]:
        findings.append(_finding(
            "audience_report_pack_view_missing",
            "No shared sourceRefs provided.",
            source_ref,
        ))

    # Confidence threshold check
    if config["confidence"] < config["limits"]["confidence_threshold"]:
        findings.append(_finding(
            "audience_report_pack_verdict_recomputed_denied",
            f"Audience report confidence {config['confidence']} below threshold {config['limits']['confidence_threshold']}.",
            source_ref,
        ))

    if diagnostics["budget_exceeded"]["views"]:
        findings.append(_finding(
            "audience_report_pack_view_budget_exceeded",
            f"Audience view count {len(config['audience_views'])} exceeds limit {config['limits']['max_views']}.",
            source_ref,
        ))

    if diagnostics["budget_exceeded"]["sourceRefs"]:
        findings.append(_finding(
            "audience_report_pack_source_ref_budget_exceeded",
            f"Shared sourceRef count {len(config['shared_sourceRefs'])} exceeds limit {config['limits']['max_sourceRefs']}.",
            source_ref,
        ))

    return findings


def _finding(code: str, message: str, source_ref: str) -> AudienceReportPackFinding:
    return AudienceReportPackFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
    )
