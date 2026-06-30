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
    findings = _findings_for(config, source_refs[0])
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
            "verdict_recomputed": config["verdict_recomputed"],
            "confidence": config["confidence"],
            "finding_count": len(findings),
        },
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
    return {
        "audience_views": audience_views,
        "shared_sourceRefs": shared_sourceRefs,
        "analysis_scope": str(config.get("analysis_scope", "") or ""),
        "verdict_recomputed": bool(config.get("verdict_recomputed", False)),
        "source_ref_drift_detected": bool(config.get("source_ref_drift_detected", False)),
        "confidence": float(config.get("confidence", 0.0) or 0.0),
        "input_refs": [str(ref) for ref in config.get("input_refs", []) if str(ref)],
        "limits": _normalize_limits(config.get("limits", {})),
    }


def _normalize_audience_view(v: dict[str, Any]) -> dict[str, Any]:
    return {
        "audience_id": str(v.get("audience_id", "") or ""),
        "view_type": str(v.get("view_type", "") or ""),
        "verdict": str(v.get("verdict", "") or ""),
        "sourceRef": str(v.get("sourceRef", "") or ""),
        "rationale": str(v.get("rationale", "") or ""),
    }


def _normalize_limits(limits: dict[str, Any]) -> dict[str, Any]:
    return {
        "confidence_threshold": float(limits.get("confidence_threshold", 0.7) or 0.7),
        "max_views": int(limits.get("max_views", 10) or 10),
        "max_sourceRefs": int(limits.get("max_sourceRefs", 50) or 50),
    }


def _findings_for(config: dict[str, Any], source_ref: str) -> list[AudienceReportPackFinding]:
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

    return findings


def _finding(code: str, message: str, source_ref: str) -> AudienceReportPackFinding:
    return AudienceReportPackFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
    )
