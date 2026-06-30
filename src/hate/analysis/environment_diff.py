"""Environment diff analysis for HATE-GAP-055."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EnvironmentDiffFinding:
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


def evaluate_environment_diff_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_environment_diff_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "environment-diff-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_environment_diff_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "environment-diff-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["environment-diff"])
    diff_config = _normalize_diff_config(input_data.get("diff_config", input_data))
    findings = _findings_for(diff_config, source_refs[0])
    status = "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": "environment-diff-report",
        "report_id": report_id,
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "diff_config": diff_config,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "delta_count": len(diff_config["environment_deltas"]),
            "drift_class_count": len(diff_config["drift_classes"]),
            "attempt_count": len(diff_config["attempts_compared"]),
            "confidence": diff_config["confidence"],
            "finding_count": len(findings),
        },
        "environment_deltas": diff_config["environment_deltas"],
        "attempts_compared": diff_config["attempts_compared"],
        "drift_classes": diff_config["drift_classes"],
        "analysis_scope": diff_config["analysis_scope"],
        "input_refs": diff_config["input_refs"],
        "confidence": diff_config["confidence"],
        "limits": diff_config["limits"],
        "sourceRefs": sorted(set(source_refs)),
    }


def _normalize_diff_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw_config or {})
    environment_deltas = [
        _normalize_environment_delta(d)
        for d in config.get("environment_deltas", [])
        if isinstance(d, dict)
    ]
    attempts_compared = [
        _normalize_attempt(a)
        for a in config.get("attempts_compared", [])
        if isinstance(a, dict)
    ]
    drift_classes = [
        _normalize_drift_class(c)
        for c in config.get("drift_classes", [])
        if isinstance(c, dict)
    ]
    return {
        "environment_deltas": environment_deltas,
        "attempts_compared": attempts_compared,
        "drift_classes": drift_classes,
        "runtime_version_drift_explained": bool(config.get("runtime_version_drift_explained", True)),
        "cache_state_known": bool(config.get("cache_state_known", True)),
        "analysis_scope": str(config.get("analysis_scope", "") or ""),
        "input_refs": [str(ref) for ref in config.get("input_refs", []) if str(ref)],
        "confidence": float(config.get("confidence", 0.0) or 0.0),
        "limits": _normalize_limits(config.get("limits", {})),
    }


def _normalize_environment_delta(d: dict[str, Any]) -> dict[str, Any]:
    return {
        "delta_id": str(d.get("delta_id", "") or ""),
        "delta_type": str(d.get("delta_type", "") or ""),
        "category": str(d.get("category", "") or ""),
        "severity": str(d.get("severity", "") or ""),
        "confidence": float(d.get("confidence", 0.0) or 0.0),
        "sourceRef": str(d.get("sourceRef", "") or ""),
        "rationale": str(d.get("rationale", "") or ""),
        "explained": bool(d.get("explained", True)),
    }


def _normalize_attempt(a: dict[str, Any]) -> dict[str, Any]:
    return {
        "attempt_id": str(a.get("attempt_id", "") or ""),
        "environment_ref": str(a.get("environment_ref", "") or ""),
        "timestamp": str(a.get("timestamp", "") or ""),
    }


def _normalize_drift_class(c: dict[str, Any]) -> dict[str, Any]:
    return {
        "class_id": str(c.get("class_id", "") or ""),
        "class_type": str(c.get("class_type", "") or ""),
        "drift_count": int(c.get("drift_count", 0) or 0),
        "severity": str(c.get("severity", "") or ""),
    }


def _normalize_limits(limits: dict[str, Any]) -> dict[str, Any]:
    return {
        "max_deltas": int(limits.get("max_deltas", 100) or 100),
        "max_attempts": int(limits.get("max_attempts", 10) or 10),
        "max_drift_classes": int(limits.get("max_drift_classes", 20) or 20),
        "confidence_threshold": float(limits.get("confidence_threshold", 0.7) or 0.7),
    }


def _findings_for(config: dict[str, Any], source_ref: str) -> list[EnvironmentDiffFinding]:
    findings: list[EnvironmentDiffFinding] = []

    # HATE-GAP-055 primary negative: unexplained drift
    runtime_drifts = [
        d for d in config["environment_deltas"]
        if d.get("delta_type") == "runtime_version_drift" and not d.get("explained")
    ]

    if runtime_drifts:
        findings.append(_finding(
            "environment_diff_unexplained_drift_hold",
            "Unexplained runtime version drift detected.",
            source_ref,
        ))

    # Additional finding: runtime_version_drift_explained flag false
    if not config["runtime_version_drift_explained"]:
        runtime_deltas = [d for d in config["environment_deltas"] if d.get("delta_type") == "runtime_version_drift"]
        if runtime_deltas:
            findings.append(_finding(
                "environment_diff_unexplained_drift_hold",
                "Runtime version drift not marked as explained.",
                source_ref,
            ))

    # Additional finding: cache_state_unknown
    if not config["cache_state_known"]:
        findings.append(_finding(
            "environment_diff_cache_state_unknown",
            "Cache state not known for environment comparison.",
            source_ref,
        ))

    # Check for missing sourceRef on deltas
    for d in config["environment_deltas"]:
        if not d.get("sourceRef"):
            findings.append(_finding(
                "environment_diff_unexplained_drift_hold",
                f"Environment delta '{d.get('delta_id')}' missing sourceRef.",
                source_ref,
            ))

    # Confidence threshold check
    if config["confidence"] < config["limits"]["confidence_threshold"]:
        findings.append(_finding(
            "environment_diff_unexplained_drift_hold",
            f"Environment diff confidence {config['confidence']} below threshold {config['limits']['confidence_threshold']}.",
            source_ref,
        ))

    return findings


def _finding(code: str, message: str, source_ref: str) -> EnvironmentDiffFinding:
    return EnvironmentDiffFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
    )