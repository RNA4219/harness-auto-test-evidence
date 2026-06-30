"""Contradiction detection analysis for HATE-GAP-056."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ContradictionFinding:
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


def evaluate_contradiction_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_contradiction_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "contradiction-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_contradiction_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "contradiction-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["contradiction"])
    config = _normalize_contradiction_config(input_data.get("contradiction_config", input_data))
    findings = _findings_for(config, source_refs[0])
    status = "blocked" if any(f.readiness_effect == "blocked" for f in findings) else "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": "contradiction-report",
        "report_id": report_id,
        "overall_status": status,
        "readiness_effect": "blocked" if status == "blocked" else "hold" if findings else "none",
        "analysis_scope": config["analysis_scope"],
        "contradiction_config": config,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "contradiction_count": len(config["contradictions"]),
            "blocking_effect_count": len(config["blocking_effects"]),
            "claim_impact_count": len(config["claim_impacts"]),
            "confidence": config["confidence"],
            "finding_count": len(findings),
        },
        "contradictions": config["contradictions"],
        "blocking_effects": config["blocking_effects"],
        "claim_impacts": config["claim_impacts"],
        "input_refs": config["input_refs"],
        "confidence": config["confidence"],
        "limits": config["limits"],
        "sourceRefs": sorted(set(source_refs)),
    }


def _normalize_contradiction_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw_config or {})
    contradictions = [
        _normalize_contradiction(c)
        for c in config.get("contradictions", [])
        if isinstance(c, dict)
    ]
    blocking_effects = [
        _normalize_blocking_effect(b)
        for b in config.get("blocking_effects", [])
        if isinstance(b, dict)
    ]
    claim_impacts = [
        _normalize_claim_impact(i)
        for i in config.get("claim_impacts", [])
        if isinstance(i, dict)
    ]
    return {
        "contradictions": contradictions,
        "blocking_effects": blocking_effects,
        "claim_impacts": claim_impacts,
        "analysis_scope": str(config.get("analysis_scope", "") or ""),
        "pass_status_with_critical": bool(config.get("pass_status_with_critical", False)),
        "critical_finding_present": bool(config.get("critical_finding_present", False)),
        "coverage_mutation_aligned": bool(config.get("coverage_mutation_aligned", True)),
        "contract_schema_aligned": bool(config.get("contract_schema_aligned", True)),
        "confidence": float(config.get("confidence", 0.0) or 0.0),
        "input_refs": [str(ref) for ref in config.get("input_refs", []) if str(ref)],
        "limits": _normalize_limits(config.get("limits", {})),
    }


def _normalize_contradiction(c: dict[str, Any]) -> dict[str, Any]:
    return {
        "contradiction_id": str(c.get("contradiction_id", "") or ""),
        "contradiction_type": str(c.get("contradiction_type", "") or ""),
        "severity": str(c.get("severity", "") or ""),
        "sourceRef": str(c.get("sourceRef", "") or ""),
        "rationale": str(c.get("rationale", "") or ""),
    }


def _normalize_blocking_effect(b: dict[str, Any]) -> dict[str, Any]:
    return {
        "effect_id": str(b.get("effect_id", "") or ""),
        "effect_type": str(b.get("effect_type", "") or ""),
        "blocked_claim": str(b.get("blocked_claim", "") or ""),
        "sourceRef": str(b.get("sourceRef", "") or ""),
    }


def _normalize_claim_impact(i: dict[str, Any]) -> dict[str, Any]:
    return {
        "claim_id": str(i.get("claim_id", "") or ""),
        "impact_type": str(i.get("impact_type", "") or ""),
        "impact_severity": str(i.get("impact_severity", "") or ""),
        "sourceRef": str(i.get("sourceRef", "") or ""),
    }


def _normalize_limits(limits: dict[str, Any]) -> dict[str, Any]:
    return {
        "confidence_threshold": float(limits.get("confidence_threshold", 0.7) or 0.7),
        "max_contradictions": int(limits.get("max_contradictions", 50) or 50),
        "max_blocking_effects": int(limits.get("max_blocking_effects", 20) or 20),
    }


def _findings_for(config: dict[str, Any], source_ref: str) -> list[ContradictionFinding]:
    findings: list[ContradictionFinding] = []

    # HATE-GAP-056 primary negative: pass with critical finding blocked
    if config.get("pass_status_with_critical") and config.get("critical_finding_present"):
        findings.append(_finding(
            "contradiction_pass_with_critical_finding_blocked",
            "Pass status contradicts critical finding presence.",
            source_ref,
            readiness_effect="blocked",
        ))

    # Coverage mutation alignment check
    if not config.get("coverage_mutation_aligned"):
        findings.append(_finding(
            "contradiction_coverage_up_mutation_down",
            "Coverage mutation alignment violated.",
            source_ref,
        ))

    # Contract schema alignment check
    if not config.get("contract_schema_aligned"):
        findings.append(_finding(
            "contradiction_contract_schema_conflict",
            "Contract schema alignment violated.",
            source_ref,
        ))

    # Check for missing sourceRef on contradictions
    for c in config["contradictions"]:
        if not c.get("sourceRef"):
            findings.append(_finding(
                "contradiction_pass_with_critical_finding_blocked",
                f"Contradiction '{c.get('contradiction_id')}' missing sourceRef.",
                source_ref,
            ))

    # Confidence threshold check
    if config["confidence"] < config["limits"]["confidence_threshold"]:
        findings.append(_finding(
            "contradiction_pass_with_critical_finding_blocked",
            f"Contradiction detection confidence {config['confidence']} below threshold {config['limits']['confidence_threshold']}.",
            source_ref,
        ))

    return findings


def _finding(
    code: str,
    message: str,
    source_ref: str,
    *,
    readiness_effect: str = "hold",
) -> ContradictionFinding:
    return ContradictionFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
        readiness_effect=readiness_effect,
    )
