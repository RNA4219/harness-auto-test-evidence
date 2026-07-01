"""Flaky classification evaluation for HATE-GAP-051."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FlakyClassificationFinding:
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


def evaluate_flaky_classification_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_flaky_classification_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "flaky-classification-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_flaky_classification_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "flaky-classification-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["flaky-classification"])
    flaky_config = _normalize_flaky_config(input_data.get("flaky_config", input_data))
    findings = _findings_for(flaky_config, source_refs[0])
    status = "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": "flaky-classification-report",
        "report_id": report_id,
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "flaky_config": flaky_config,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "flake_class_count": len(flaky_config["flake_classes"]),
            "attempt_history_count": len(flaky_config["attempt_history"]),
            "environment_evidence_count": len(flaky_config["environment_evidence"]),
            "confidence": flaky_config["confidence"],
            "finding_count": len(findings),
        },
        "analysis_scope": flaky_config["analysis_scope"],
        "input_refs": flaky_config["input_refs"],
        "confidence": flaky_config["confidence"],
        "limits": flaky_config["limits"],
        "sourceRefs": sorted(set(source_refs)),
    }


def _normalize_flaky_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw_config or {})
    flake_classes = [
        _normalize_flake_class(fc)
        for fc in config.get("flake_classes", [])
        if isinstance(fc, dict)
    ]
    attempt_history = [
        _normalize_attempt(attempt)
        for attempt in config.get("attempt_history", [])
        if isinstance(attempt, dict)
    ]
    environment_evidence = [
        _normalize_env_evidence(ee)
        for ee in config.get("environment_evidence", [])
        if isinstance(ee, dict)
    ]
    return {
        "flake_classes": flake_classes,
        "attempt_history": attempt_history,
        "environment_evidence": environment_evidence,
        "analysis_scope": str(config.get("analysis_scope", "") or ""),
        "input_refs": [str(ref) for ref in config.get("input_refs", []) if str(ref)],
        "confidence": float(config.get("confidence", 0.0) or 0.0),
        "limits": _normalize_limits(config.get("limits", {})),
        "class_taxonomy_available": bool(config.get("class_taxonomy_available", False)),
        "retry_history_available": bool(config.get("retry_history_available", False)),
        "environment_evidence_available": bool(config.get("environment_evidence_available", False)),
    }


def _normalize_flake_class(fc: dict[str, Any]) -> dict[str, Any]:
    return {
        "class_id": str(fc.get("class_id", "") or ""),
        "class_name": str(fc.get("class_name", "") or ""),
        "confidence": float(fc.get("confidence", 0.0) or 0.0),
        "sourceRef": str(fc.get("sourceRef", "") or ""),
        "rationale": str(fc.get("rationale", "") or ""),
        "verified": bool(fc.get("verified", True)),
    }


def _normalize_attempt(attempt: dict[str, Any]) -> dict[str, Any]:
    return {
        "attempt_id": str(attempt.get("attempt_id", "") or ""),
        "test_id": str(attempt.get("test_id", "") or ""),
        "outcome": str(attempt.get("outcome", "") or ""),
        "confidence": float(attempt.get("confidence", 0.0) or 0.0),
        "sourceRef": str(attempt.get("sourceRef", "") or ""),
        "rationale": str(attempt.get("rationale", "") or ""),
    }


def _normalize_env_evidence(ee: dict[str, Any]) -> dict[str, Any]:
    return {
        "evidence_id": str(ee.get("evidence_id", "") or ""),
        "delta_type": str(ee.get("delta_type", "") or ""),
        "confidence": float(ee.get("confidence", 0.0) or 0.0),
        "sourceRef": str(ee.get("sourceRef", "") or ""),
        "rationale": str(ee.get("rationale", "") or ""),
        "verified": bool(ee.get("verified", True)),
    }


def _normalize_limits(limits: dict[str, Any]) -> dict[str, Any]:
    return {
        "max_flake_classes": int(limits.get("max_flake_classes", 100) or 100),
        "max_attempts": int(limits.get("max_attempts", 1000) or 1000),
        "confidence_threshold": float(limits.get("confidence_threshold", 0.7) or 0.7),
    }


def _findings_for(config: dict[str, Any], source_ref: str) -> list[FlakyClassificationFinding]:
    findings: list[FlakyClassificationFinding] = []

    # HATE-GAP-051 primary negative: unknown flake hold
    if not config["class_taxonomy_available"]:
        findings.append(_finding(
            "flaky_classification_unknown_flake_hold",
            "Flaky classification requires class taxonomy for classification.",
            source_ref,
        ))

    # Additional finding codes from vocabulary
    if not config["environment_evidence_available"]:
        findings.append(_finding(
            "flaky_classification_environment_evidence_missing",
            "Flaky classification requires environment evidence for classification.",
            source_ref,
        ))

    if not config["retry_history_available"]:
        findings.append(_finding(
            "flaky_classification_retry_history_missing",
            "Flaky classification requires retry history for classification.",
            source_ref,
        ))

    for fc in config["flake_classes"]:
        if not fc.get("verified"):
            findings.append(_finding(
                "flaky_classification_unknown_flake_hold",
                f"Flake class '{fc.get('class_name')}' not verified against taxonomy.",
                source_ref,
            ))

    for ee in config["environment_evidence"]:
        if not ee.get("sourceRef"):
            findings.append(_finding(
                "flaky_classification_environment_evidence_missing",
                f"Environment evidence '{ee.get('evidence_id')}' missing sourceRef.",
                source_ref,
            ))

    for attempt in config["attempt_history"]:
        if not attempt.get("sourceRef"):
            findings.append(_finding(
                "flaky_classification_retry_history_missing",
                f"Attempt '{attempt.get('attempt_id')}' missing sourceRef.",
                source_ref,
            ))

    if config["confidence"] < config["limits"]["confidence_threshold"]:
        findings.append(_finding(
            "flaky_classification_unknown_flake_hold",
            f"Flaky classification confidence {config['confidence']} below threshold {config['limits']['confidence_threshold']}.",
            source_ref,
        ))

    return findings


def _finding(code: str, message: str, source_ref: str) -> FlakyClassificationFinding:
    return FlakyClassificationFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
    )
