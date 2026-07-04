"""Oracle classification evaluation for HATE-GAP-052."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OracleClassificationFinding:
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


def evaluate_oracle_classification_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_oracle_classification_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "oracle-classification-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_oracle_classification_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "oracle-classification-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["oracle-classification"])
    oracle_config = _normalize_oracle_config(input_data.get("oracle_config", input_data))
    diagnostics = _derive_diagnostics(oracle_config)
    findings = _findings_for(oracle_config, diagnostics, source_refs[0])
    status = "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": "oracle-classification-report",
        "report_id": report_id,
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "oracle_config": oracle_config,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "oracle_class_count": len(oracle_config["oracle_classes"]),
            "semantic_guard_count": len(oracle_config["semantic_guards"]),
            "no_oracle_risk_count": len(oracle_config["no_oracle_risks"]),
            "test_source_count": len(oracle_config["test_sources"]),
            "inferred_oracle_count": len(diagnostics["inferred_oracles"]),
            "weak_oracle_count": len(diagnostics["weak_oracle_test_ids"]),
            "no_oracle_test_count": len(diagnostics["no_oracle_test_ids"]),
            "confidence": oracle_config["confidence"],
            "finding_count": len(findings),
        },
        "inferred_oracles": diagnostics["inferred_oracles"],
        "oracle_classification_diagnostics": diagnostics,
        "analysis_scope": oracle_config["analysis_scope"],
        "input_refs": oracle_config["input_refs"],
        "confidence": oracle_config["confidence"],
        "limits": oracle_config["limits"],
        "sourceRefs": sorted(set(source_refs)),
    }


def _normalize_oracle_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw_config or {})
    oracle_classes = [
        _normalize_oracle_class(oc)
        for oc in config.get("oracle_classes", [])
        if isinstance(oc, dict)
    ]
    semantic_guards = [
        _normalize_semantic_guard(sg)
        for sg in config.get("semantic_guards", [])
        if isinstance(sg, dict)
    ]
    no_oracle_risks = [
        _normalize_no_oracle_risk(nor)
        for nor in config.get("no_oracle_risks", [])
        if isinstance(nor, dict)
    ]
    test_sources = [
        _normalize_test_source(ts)
        for ts in config.get("test_sources", [])
        if isinstance(ts, dict)
    ]
    return {
        "oracle_classes": oracle_classes,
        "semantic_guards": semantic_guards,
        "no_oracle_risks": no_oracle_risks,
        "test_sources": test_sources,
        "analysis_scope": str(config.get("analysis_scope", "") or ""),
        "input_refs": [str(ref) for ref in config.get("input_refs", []) if str(ref)],
        "confidence": float(config.get("confidence", 0.0) or 0.0),
        "limits": _normalize_limits(config.get("limits", {})),
        "oracle_taxonomy_available": bool(config.get("oracle_taxonomy_available", False)),
        "semantic_guard_available": bool(config.get("semantic_guard_available", False)),
        "critical_risk_coverage_available": bool(config.get("critical_risk_coverage_available", False)),
    }


def _normalize_oracle_class(oc: dict[str, Any]) -> dict[str, Any]:
    return {
        "oracle_id": str(oc.get("oracle_id", "") or ""),
        "oracle_type": str(oc.get("oracle_type", "") or ""),
        "target_risk": str(oc.get("target_risk", "") or ""),
        "confidence": float(oc.get("confidence", 0.0) or 0.0),
        "sourceRef": str(oc.get("sourceRef", "") or ""),
        "rationale": str(oc.get("rationale", "") or ""),
        "verified": bool(oc.get("verified", True)),
    }


def _normalize_semantic_guard(sg: dict[str, Any]) -> dict[str, Any]:
    return {
        "guard_id": str(sg.get("guard_id", "") or ""),
        "guard_type": str(sg.get("guard_type", "") or ""),
        "target_behavior": str(sg.get("target_behavior", "") or ""),
        "confidence": float(sg.get("confidence", 0.0) or 0.0),
        "sourceRef": str(sg.get("sourceRef", "") or ""),
        "rationale": str(sg.get("rationale", "") or ""),
        "verified": bool(sg.get("verified", True)),
    }


def _normalize_no_oracle_risk(nor: dict[str, Any]) -> dict[str, Any]:
    return {
        "risk_id": str(nor.get("risk_id", "") or ""),
        "risk_type": str(nor.get("risk_type", "") or ""),
        "severity": str(nor.get("severity", "") or ""),
        "confidence": float(nor.get("confidence", 0.0) or 0.0),
        "sourceRef": str(nor.get("sourceRef", "") or ""),
        "rationale": str(nor.get("rationale", "") or ""),
        "mitigated": bool(nor.get("mitigated", False)),
    }


def _normalize_test_source(ts: dict[str, Any]) -> dict[str, Any]:
    return {
        "test_id": str(ts.get("test_id", "") or ""),
        "target_risk": str(ts.get("target_risk", "") or ""),
        "severity": str(ts.get("severity", "") or ""),
        "sourceRef": str(ts.get("sourceRef", "") or ""),
        "text": str(ts.get("text", "") or ""),
    }


def _normalize_limits(limits: dict[str, Any]) -> dict[str, Any]:
    return {
        "max_oracle_classes": int(limits.get("max_oracle_classes", 100) or 100),
        "max_semantic_guards": int(limits.get("max_semantic_guards", 100) or 100),
        "max_no_oracle_risks": int(limits.get("max_no_oracle_risks", 100) or 100),
        "confidence_threshold": float(limits.get("confidence_threshold", 0.7) or 0.7),
    }


def _derive_diagnostics(config: dict[str, Any]) -> dict[str, Any]:
    inferred = [_infer_oracle(source) for source in config["test_sources"]]
    weak_types = {"snapshot", "truthiness", "no_exception", "coverage_only"}
    weak_oracle_test_ids = sorted(o["test_id"] for o in inferred if o["oracle_type"] in weak_types and o["test_id"])
    no_oracle_test_ids = sorted(o["test_id"] for o in inferred if o["oracle_type"] == "no_oracle" and o["test_id"])
    critical_without_strong = sorted(
        o["test_id"]
        for o in inferred
        if o["severity"] == "critical" and o["oracle_type"] in weak_types | {"no_oracle"}
    )
    duplicate_oracle_ids = _duplicates([oc["oracle_id"] for oc in config["oracle_classes"] if oc["oracle_id"]])
    missing_source_ref_ids = sorted(
        [
            *[oc["oracle_id"] for oc in config["oracle_classes"] if oc["oracle_id"] and not oc["sourceRef"]],
            *[sg["guard_id"] for sg in config["semantic_guards"] if sg["guard_id"] and not sg["sourceRef"]],
            *[nor["risk_id"] for nor in config["no_oracle_risks"] if nor["risk_id"] and not nor["sourceRef"]],
            *[ts["test_id"] for ts in config["test_sources"] if ts["test_id"] and not ts["sourceRef"]],
        ]
    )
    return {
        "inferred_oracles": inferred,
        "weak_oracle_test_ids": weak_oracle_test_ids,
        "no_oracle_test_ids": no_oracle_test_ids,
        "critical_without_strong_oracle_test_ids": critical_without_strong,
        "duplicate_oracle_ids": sorted(duplicate_oracle_ids),
        "missing_source_ref_ids": missing_source_ref_ids,
    }


def _infer_oracle(source: dict[str, Any]) -> dict[str, Any]:
    text = source["text"].lower()
    oracle_type = "no_oracle"
    confidence = 0.4
    if "hypothesis" in text or "given(" in text or "property" in text:
        oracle_type = "property"
        confidence = 0.86
    elif "metamorphic" in text or "roundtrip" in text or "inverse" in text:
        oracle_type = "metamorphic"
        confidence = 0.84
    elif "pact" in text or "contract" in text or "schema" in text:
        oracle_type = "contract"
        confidence = 0.83
    elif "mutation score" in text or "mutmut" in text or "stryker" in text:
        oracle_type = "mutation_backed"
        confidence = 0.82
    elif "manual approval" in text or "human review" in text:
        oracle_type = "manual"
        confidence = 0.7
    elif "snapshot" in text or "to_match_snapshot" in text or "matchsnapshot" in text:
        oracle_type = "snapshot"
        confidence = 0.65
    elif "==" in text or "tobe(" in text or "toequal(" in text or "assert_equal" in text:
        oracle_type = "exact"
        confidence = 0.8
    elif "tobetruthy" in text or "assert true" in text or "assert result" in text:
        oracle_type = "truthiness"
        confidence = 0.55
    elif "does not raise" in text or "not.to.throw" in text or "pytest.raises" not in text and "run only" in text:
        oracle_type = "no_exception"
        confidence = 0.5
    return {
        "test_id": source["test_id"],
        "target_risk": source["target_risk"],
        "severity": source["severity"],
        "oracle_type": oracle_type,
        "confidence": confidence,
        "sourceRef": source["sourceRef"],
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
) -> list[OracleClassificationFinding]:
    findings: list[OracleClassificationFinding] = []

    # HATE-GAP-052 primary negative: snapshot-only-critical-hold
    snapshot_oracles = [oc for oc in config["oracle_classes"] if oc.get("oracle_type") == "snapshot"]
    critical_no_oracle_risks = [nor for nor in config["no_oracle_risks"] if nor.get("severity") == "critical" and not nor.get("mitigated")]

    if snapshot_oracles and critical_no_oracle_risks and not config.get("semantic_guard_available"):
        findings.append(_finding(
            "oracle_classification_snapshot_only_critical_hold",
            "Snapshot-only oracle for critical risk requires semantic guard.",
            source_ref,
        ))

    if diagnostics["critical_without_strong_oracle_test_ids"]:
        findings.append(_finding(
            "oracle_classification_snapshot_only_critical_hold",
            f"Critical tests lack strong oracle: {', '.join(diagnostics['critical_without_strong_oracle_test_ids'])}.",
            source_ref,
        ))

    if diagnostics["no_oracle_test_ids"]:
        findings.append(_finding(
            "oracle_classification_no_oracle_for_required_risk",
            f"Tests have no detected oracle: {', '.join(diagnostics['no_oracle_test_ids'])}.",
            source_ref,
        ))

    weak_noncritical = sorted(set(diagnostics["weak_oracle_test_ids"]) - set(diagnostics["critical_without_strong_oracle_test_ids"]))
    if weak_noncritical:
        findings.append(_finding(
            "oracle_classification_weak_oracle_hold",
            f"Weak oracle detected in tests: {', '.join(weak_noncritical)}.",
            source_ref,
        ))

    if diagnostics["duplicate_oracle_ids"]:
        findings.append(_finding(
            "oracle_classification_duplicate_oracle_id",
            f"Duplicate oracle ids detected: {', '.join(diagnostics['duplicate_oracle_ids'])}.",
            source_ref,
        ))

    # Additional finding codes from vocabulary
    if not config["oracle_taxonomy_available"]:
        findings.append(_finding(
            "oracle_classification_taxonomy_missing",
            "Oracle classification requires an oracle taxonomy.",
            source_ref,
        ))

    if not config["semantic_guard_available"]:
        findings.append(_finding(
            "oracle_classification_semantic_guard_missing",
            "Oracle classification requires semantic guard evidence.",
            source_ref,
        ))

    if not config["critical_risk_coverage_available"]:
        findings.append(_finding(
            "oracle_classification_critical_coverage_missing",
            "Oracle classification requires critical risk coverage evidence.",
            source_ref,
        ))

    for nor in config["no_oracle_risks"]:
        if nor.get("severity") == "critical" and not nor.get("mitigated"):
            findings.append(_finding(
                "oracle_classification_no_oracle_for_required_risk",
                f"Critical risk '{nor.get('risk_id')}' has no oracle.",
                source_ref,
            ))

    for oc in config["oracle_classes"]:
        if not oc.get("verified"):
            findings.append(_finding(
                "oracle_classification_snapshot_only_critical_hold",
                f"Oracle class '{oc.get('oracle_id')}' not verified against taxonomy.",
                source_ref,
            ))

    for sg in config["semantic_guards"]:
        if not sg.get("sourceRef"):
            findings.append(_finding(
                "oracle_classification_semantic_guard_missing",
                f"Semantic guard '{sg.get('guard_id')}' missing sourceRef.",
                source_ref,
            ))

    for oc in config["oracle_classes"]:
        if not oc.get("sourceRef"):
            findings.append(_finding(
                "oracle_classification_source_ref_missing",
                f"Oracle class '{oc.get('oracle_id')}' missing sourceRef.",
                source_ref,
            ))

    for nor in config["no_oracle_risks"]:
        if not nor.get("sourceRef"):
            findings.append(_finding(
                "oracle_classification_no_oracle_for_required_risk",
                f"No-oracle risk '{nor.get('risk_id')}' missing sourceRef.",
                source_ref,
            ))

    for test_id in [ts["test_id"] for ts in config["test_sources"] if ts["test_id"] and not ts["sourceRef"]]:
        findings.append(_finding(
            "oracle_classification_source_ref_missing",
            f"Test source '{test_id}' missing sourceRef.",
            source_ref,
        ))

    if len(config["oracle_classes"]) > config["limits"]["max_oracle_classes"]:
        findings.append(_finding(
            "oracle_classification_oracle_budget_exceeded",
            f"Oracle class count {len(config['oracle_classes'])} exceeds limit {config['limits']['max_oracle_classes']}.",
            source_ref,
        ))

    if len(config["semantic_guards"]) > config["limits"]["max_semantic_guards"]:
        findings.append(_finding(
            "oracle_classification_guard_budget_exceeded",
            f"Semantic guard count {len(config['semantic_guards'])} exceeds limit {config['limits']['max_semantic_guards']}.",
            source_ref,
        ))

    if len(config["no_oracle_risks"]) > config["limits"]["max_no_oracle_risks"]:
        findings.append(_finding(
            "oracle_classification_no_oracle_risk_budget_exceeded",
            f"No-oracle risk count {len(config['no_oracle_risks'])} exceeds limit {config['limits']['max_no_oracle_risks']}.",
            source_ref,
        ))

    if config["confidence"] < config["limits"]["confidence_threshold"]:
        findings.append(_finding(
            "oracle_classification_snapshot_only_critical_hold",
            f"Oracle classification confidence {config['confidence']} below threshold {config['limits']['confidence_threshold']}.",
            source_ref,
        ))

    return findings


def _finding(code: str, message: str, source_ref: str) -> OracleClassificationFinding:
    return OracleClassificationFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
    )
