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
    diagnostics = _derive_diagnostics(flaky_config)
    findings = _findings_for(flaky_config, diagnostics, source_refs[0])
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
            "classified_test_count": len(diagnostics["classified_tests"]),
            "unknown_flake_count": len(diagnostics["unknown_test_ids"]),
            "mixed_outcome_test_count": len(diagnostics["mixed_outcome_test_ids"]),
            "duplicate_attempt_count": len(diagnostics["duplicate_attempt_ids"]),
            "confidence": flaky_config["confidence"],
            "finding_count": len(findings),
        },
        "classified_tests": diagnostics["classified_tests"],
        "flaky_classification_diagnostics": diagnostics,
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
        "duration_ms": float(attempt.get("duration_ms", 0.0) or 0.0),
        "error_signature": str(attempt.get("error_signature", "") or ""),
        "environment_ref": str(attempt.get("environment_ref", "") or ""),
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
        "max_environment_evidence": int(limits.get("max_environment_evidence", 100) or 100),
        "confidence_threshold": float(limits.get("confidence_threshold", 0.7) or 0.7),
        "min_attempts_for_flake": int(limits.get("min_attempts_for_flake", 2) or 2),
    }


def _derive_diagnostics(config: dict[str, Any]) -> dict[str, Any]:
    attempts_by_test: dict[str, list[dict[str, Any]]] = {}
    attempt_ids = [attempt["attempt_id"] for attempt in config["attempt_history"] if attempt["attempt_id"]]
    for attempt in config["attempt_history"]:
        test_id = attempt["test_id"] or "_unknown"
        attempts_by_test.setdefault(test_id, []).append(attempt)

    env_delta_types = {_canonical_delta_type(e["delta_type"]) for e in config["environment_evidence"] if e["verified"]}
    classified_tests: dict[str, dict[str, Any]] = {}
    unknown_test_ids: list[str] = []
    mixed_outcome_test_ids: list[str] = []
    for test_id, attempts in attempts_by_test.items():
        outcomes = {a["outcome"] for a in attempts if a["outcome"]}
        if len(attempts) < config["limits"]["min_attempts_for_flake"]:
            unknown_test_ids.append(test_id)
            continue
        if {"pass", "passed"} & outcomes and {"fail", "failed", "error", "timeout"} & outcomes:
            mixed_outcome_test_ids.append(test_id)
        classification = _classify_attempts(attempts, env_delta_types)
        classified_tests[test_id] = classification
        if classification["class_name"] == "unknown":
            unknown_test_ids.append(test_id)

    return {
        "classified_tests": classified_tests,
        "unknown_test_ids": sorted(set(unknown_test_ids)),
        "mixed_outcome_test_ids": sorted(set(mixed_outcome_test_ids)),
        "duplicate_attempt_ids": sorted(_duplicates(attempt_ids)),
        "unverified_environment_evidence_ids": sorted(
            e["evidence_id"] for e in config["environment_evidence"] if e["evidence_id"] and not e["verified"]
        ),
    }


def _canonical_delta_type(delta_type: str) -> str:
    lowered = delta_type.lower()
    if "runtime" in lowered:
        return "runtime"
    if "container" in lowered:
        return "container"
    if "cache" in lowered:
        return "cache"
    if "dependency" in lowered:
        return "dependency"
    if "browser" in lowered:
        return "browser"
    if lowered in {"os", "runner_os", "kernel"}:
        return "os"
    return lowered


def _classify_attempts(attempts: list[dict[str, Any]], env_delta_types: set[str]) -> dict[str, Any]:
    text = " ".join([a["error_signature"].lower() + " " + a["rationale"].lower() for a in attempts])
    outcomes = {a["outcome"] for a in attempts}
    class_name = "unknown"
    confidence = 0.5
    if any("timeout" in (a["outcome"] + " " + a["error_signature"]).lower() for a in attempts):
        class_name = "timeout"
        confidence = 0.82
    elif {"runtime", "os", "container", "cache", "dependency", "browser"} & env_delta_types:
        class_name = "environment"
        confidence = 0.84
    elif "order" in text or "shared_state" in text or "depends on previous" in text:
        class_name = "order_dependence"
        confidence = 0.8
    elif "connection reset" in text or "network" in text or "econnreset" in text:
        class_name = "infrastructure"
        confidence = 0.78
    elif (
        {"pass", "passed"} & outcomes
        and {"fail", "failed", "error"} & outcomes
        and any(token in text for token in ("fixture", "data", "assert", "shared state", "test code"))
    ):
        class_name = "test_code_or_data"
        confidence = 0.72
    return {
        "class_name": class_name,
        "confidence": confidence,
        "attempt_count": len(attempts),
        "outcomes": sorted(outcomes),
    }


def _duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return duplicates


def _findings_for(
    config: dict[str, Any],
    diagnostics: dict[str, Any],
    source_ref: str,
) -> list[FlakyClassificationFinding]:
    findings: list[FlakyClassificationFinding] = []

    # HATE-GAP-051 primary negative: unknown flake hold
    if not config["class_taxonomy_available"]:
        findings.append(_finding(
            "flaky_classification_unknown_flake_hold",
            "Flaky classification requires class taxonomy for classification.",
            source_ref,
        ))

    if diagnostics["unknown_test_ids"]:
        findings.append(_finding(
            "flaky_classification_unknown_flake_hold",
            f"Flaky tests could not be classified: {', '.join(diagnostics['unknown_test_ids'])}.",
            source_ref,
        ))

    unclassified_mixed = sorted(set(diagnostics["mixed_outcome_test_ids"]) & set(diagnostics["unknown_test_ids"]))
    if unclassified_mixed:
        findings.append(_finding(
            "flaky_classification_mixed_outcome_detected",
            f"Tests have mixed pass/fail outcomes without a supported flake class: {', '.join(unclassified_mixed)}.",
            source_ref,
        ))

    if diagnostics["duplicate_attempt_ids"]:
        findings.append(_finding(
            "flaky_classification_duplicate_attempt_id",
            f"Duplicate attempt ids detected: {', '.join(diagnostics['duplicate_attempt_ids'])}.",
            source_ref,
        ))

    if diagnostics["unverified_environment_evidence_ids"]:
        findings.append(_finding(
            "flaky_classification_environment_evidence_missing",
            f"Environment evidence is not verified: {', '.join(diagnostics['unverified_environment_evidence_ids'])}.",
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

    if len(config["flake_classes"]) > config["limits"]["max_flake_classes"]:
        findings.append(_finding(
            "flaky_classification_class_budget_exceeded",
            f"Flake class count {len(config['flake_classes'])} exceeds limit {config['limits']['max_flake_classes']}.",
            source_ref,
        ))

    if len(config["attempt_history"]) > config["limits"]["max_attempts"]:
        findings.append(_finding(
            "flaky_classification_attempt_budget_exceeded",
            f"Attempt count {len(config['attempt_history'])} exceeds limit {config['limits']['max_attempts']}.",
            source_ref,
        ))

    if len(config["environment_evidence"]) > config["limits"]["max_environment_evidence"]:
        findings.append(_finding(
            "flaky_classification_environment_budget_exceeded",
            f"Environment evidence count {len(config['environment_evidence'])} exceeds limit {config['limits']['max_environment_evidence']}.",
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
