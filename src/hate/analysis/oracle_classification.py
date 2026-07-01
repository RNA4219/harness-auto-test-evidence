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
    findings = _findings_for(oracle_config, source_refs[0])
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
            "confidence": oracle_config["confidence"],
            "finding_count": len(findings),
        },
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
    return {
        "oracle_classes": oracle_classes,
        "semantic_guards": semantic_guards,
        "no_oracle_risks": no_oracle_risks,
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


def _normalize_limits(limits: dict[str, Any]) -> dict[str, Any]:
    return {
        "max_oracle_classes": int(limits.get("max_oracle_classes", 100) or 100),
        "max_semantic_guards": int(limits.get("max_semantic_guards", 100) or 100),
        "max_no_oracle_risks": int(limits.get("max_no_oracle_risks", 100) or 100),
        "confidence_threshold": float(limits.get("confidence_threshold", 0.7) or 0.7),
    }


def _findings_for(config: dict[str, Any], source_ref: str) -> list[OracleClassificationFinding]:
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

    for nor in config["no_oracle_risks"]:
        if not nor.get("sourceRef"):
            findings.append(_finding(
                "oracle_classification_no_oracle_for_required_risk",
                f"No-oracle risk '{nor.get('risk_id')}' missing sourceRef.",
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
