"""Adapter capability diff analysis for HATE-GAP-060."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AdapterCapabilityDiffFinding:
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


def evaluate_adapter_capability_diff_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_adapter_capability_diff_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "adapter-capability-diff-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_adapter_capability_diff_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "adapter-capability-diff-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["adapter-capability-diff"])
    config = _normalize_adapter_config(input_data.get("adapter_config", input_data))
    findings = _findings_for(config, source_refs[0])
    status = "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": "adapter-capability-diff-report",
        "report_id": report_id,
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "analysis_scope": config["analysis_scope"],
        "adapter_config": config,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "raw_field_count": len(config["raw_field_map"]),
            "normalized_field_count": len(config["normalized_field_map"]),
            "lossy_transform_count": len(config["lossy_transforms"]),
            "confidence": config["confidence"],
            "finding_count": len(findings),
        },
        "raw_field_map": config["raw_field_map"],
        "normalized_field_map": config["normalized_field_map"],
        "lossy_transforms": config["lossy_transforms"],
        "input_refs": config["input_refs"],
        "confidence": config["confidence"],
        "limits": config["limits"],
        "sourceRefs": sorted(set(source_refs)),
    }


def _normalize_adapter_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw_config or {})
    raw_field_map = dict(config.get("raw_field_map", {}) or {})
    normalized_field_map = dict(config.get("normalized_field_map", {}) or {})
    lossy_transforms = [
        _normalize_lossy_transform(t)
        for t in config.get("lossy_transforms", [])
        if isinstance(t, dict)
    ]
    return {
        "raw_field_map": raw_field_map,
        "normalized_field_map": normalized_field_map,
        "lossy_transforms": lossy_transforms,
        "analysis_scope": str(config.get("analysis_scope", "") or ""),
        "lossy_field_drop_detected": bool(config.get("lossy_field_drop_detected", False)),
        "claim_drift_detected": bool(config.get("claim_drift_detected", False)),
        "unsupported_dialect_detected": bool(config.get("unsupported_dialect_detected", False)),
        "confidence": float(config.get("confidence", 0.0) or 0.0),
        "input_refs": [str(ref) for ref in config.get("input_refs", []) if str(ref)],
        "limits": _normalize_limits(config.get("limits", {})),
    }


def _normalize_lossy_transform(t: dict[str, Any]) -> dict[str, Any]:
    return {
        "transform_id": str(t.get("transform_id", "") or ""),
        "field_name": str(t.get("field_name", "") or ""),
        "transform_type": str(t.get("transform_type", "") or ""),
        "loss_type": str(t.get("loss_type", "") or ""),
        "sourceRef": str(t.get("sourceRef", "") or ""),
    }


def _normalize_limits(limits: dict[str, Any]) -> dict[str, Any]:
    return {
        "confidence_threshold": float(limits.get("confidence_threshold", 0.7) or 0.7),
        "max_transforms": int(limits.get("max_transforms", 50) or 50),
        "max_field_drops": int(limits.get("max_field_drops", 10) or 10),
    }


def _findings_for(config: dict[str, Any], source_ref: str) -> list[AdapterCapabilityDiffFinding]:
    findings: list[AdapterCapabilityDiffFinding] = []

    raw_fields = set(config["raw_field_map"].keys())
    normalized_fields = set(config["normalized_field_map"].keys())
    dropped_fields = raw_fields - normalized_fields

    # HATE-GAP-060 primary negative: lossy field drop
    # Trigger: lossy_field_drop_detected, len(lossy_transforms) > 0, or dropped_fields
    if config.get("lossy_field_drop_detected") or len(config["lossy_transforms"]) > 0 or dropped_fields:
        findings.append(_finding(
            "adapter_capability_diff_lossy_field_drop_hold",
            f"Lossy field drop detected: {len(dropped_fields)} fields dropped, {len(config['lossy_transforms'])} transforms.",
            source_ref,
        ))

    # Claim drift detection
    if config.get("claim_drift_detected"):
        findings.append(_finding(
            "adapter_capability_diff_claim_drift",
            "Claim drift detected in adapter normalization.",
            source_ref,
        ))

    # Unsupported dialect detection
    if config.get("unsupported_dialect_detected"):
        findings.append(_finding(
            "adapter_capability_diff_unsupported_dialect_feature",
            "Unsupported dialect feature detected in adapter.",
            source_ref,
        ))

    # Check for missing sourceRef on lossy transforms
    for t in config["lossy_transforms"]:
        if not t.get("sourceRef"):
            findings.append(_finding(
                "adapter_capability_diff_lossy_field_drop_hold",
                f"Lossy transform '{t.get('transform_id')}' missing sourceRef.",
                source_ref,
            ))

    # Confidence threshold check
    if config["confidence"] < config["limits"]["confidence_threshold"]:
        findings.append(_finding(
            "adapter_capability_diff_lossy_field_drop_hold",
            f"Adapter capability diff confidence {config['confidence']} below threshold {config['limits']['confidence_threshold']}.",
            source_ref,
        ))

    return findings


def _finding(code: str, message: str, source_ref: str) -> AdapterCapabilityDiffFinding:
    return AdapterCapabilityDiffFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
    )
