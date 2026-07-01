"""Evidence synthesis evaluation for HATE-GAP-053."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EvidenceSynthesisFinding:
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


def evaluate_evidence_synthesis_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_evidence_synthesis_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "evidence-synthesis-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_evidence_synthesis_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "evidence-synthesis-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["evidence-synthesis"])
    synthesis_config = _normalize_synthesis_config(input_data.get("synthesis_config", input_data))
    findings = _findings_for(synthesis_config, source_refs[0])
    status = "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": "evidence-synthesis-report",
        "report_id": report_id,
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "synthesis_config": synthesis_config,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "evidence_source_count": len(synthesis_config["evidence_sources"]),
            "mutation_coverage_count": len(synthesis_config["mutation_coverage"]),
            "contract_coverage_count": len(synthesis_config["contract_coverage"]),
            "confidence": synthesis_config["confidence"],
            "finding_count": len(findings),
        },
        "analysis_scope": synthesis_config["analysis_scope"],
        "input_refs": synthesis_config["input_refs"],
        "confidence": synthesis_config["confidence"],
        "limits": synthesis_config["limits"],
        "sourceRefs": sorted(set(source_refs)),
    }


def _normalize_synthesis_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw_config or {})
    evidence_sources = [
        _normalize_evidence_source(es)
        for es in config.get("evidence_sources", [])
        if isinstance(es, dict)
    ]
    mutation_coverage = [
        _normalize_mutation_coverage(mc)
        for mc in config.get("mutation_coverage", [])
        if isinstance(mc, dict)
    ]
    contract_coverage = [
        _normalize_contract_coverage(cc)
        for cc in config.get("contract_coverage", [])
        if isinstance(cc, dict)
    ]
    return {
        "evidence_sources": evidence_sources,
        "mutation_coverage": mutation_coverage,
        "contract_coverage": contract_coverage,
        "analysis_scope": str(config.get("analysis_scope", "") or ""),
        "input_refs": [str(ref) for ref in config.get("input_refs", []) if str(ref)],
        "confidence": float(config.get("confidence", 0.0) or 0.0),
        "limits": _normalize_limits(config.get("limits", {})),
        "mutation_evidence_available": bool(config.get("mutation_evidence_available", False)),
        "contract_evidence_available": bool(config.get("contract_evidence_available", False)),
        "strong_evidence_threshold": float(config.get("strong_evidence_threshold", 0.8) or 0.8),
    }


def _normalize_evidence_source(es: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_id": str(es.get("source_id", "") or ""),
        "source_type": str(es.get("source_type", "") or ""),
        "target_requirement": str(es.get("target_requirement", "") or ""),
        "confidence": float(es.get("confidence", 0.0) or 0.0),
        "sourceRef": str(es.get("sourceRef", "") or ""),
        "rationale": str(es.get("rationale", "") or ""),
        "verified": bool(es.get("verified", True)),
    }


def _normalize_mutation_coverage(mc: dict[str, Any]) -> dict[str, Any]:
    return {
        "mutation_id": str(mc.get("mutation_id", "") or ""),
        "mutation_type": str(mc.get("mutation_type", "") or ""),
        "killed": bool(mc.get("killed", True)),
        "confidence": float(mc.get("confidence", 0.0) or 0.0),
        "sourceRef": str(mc.get("sourceRef", "") or ""),
        "rationale": str(mc.get("rationale", "") or ""),
    }


def _normalize_contract_coverage(cc: dict[str, Any]) -> dict[str, Any]:
    return {
        "contract_id": str(cc.get("contract_id", "") or ""),
        "contract_type": str(cc.get("contract_type", "") or ""),
        "satisfied": bool(cc.get("satisfied", True)),
        "confidence": float(cc.get("confidence", 0.0) or 0.0),
        "sourceRef": str(cc.get("sourceRef", "") or ""),
        "rationale": str(cc.get("rationale", "") or ""),
    }


def _normalize_limits(limits: dict[str, Any]) -> dict[str, Any]:
    return {
        "max_evidence_sources": int(limits.get("max_evidence_sources", 100) or 100),
        "max_mutation_coverage": int(limits.get("max_mutation_coverage", 1000) or 1000),
        "max_contract_coverage": int(limits.get("max_contract_coverage", 100) or 100),
        "confidence_threshold": float(limits.get("confidence_threshold", 0.7) or 0.7),
    }


def _findings_for(config: dict[str, Any], source_ref: str) -> list[EvidenceSynthesisFinding]:
    findings: list[EvidenceSynthesisFinding] = []

    # HATE-GAP-053 primary negative: weak-evidence-inflation-denied
    strong_sources = [es for es in config["evidence_sources"] if es.get("confidence") >= config.get("strong_evidence_threshold", 0.8)]
    weak_sources_only = len(config["evidence_sources"]) > 0 and not strong_sources

    if weak_sources_only:
        findings.append(_finding(
            "evidence_synthesis_weak_evidence_inflation_denied",
            "Evidence synthesis cannot inflate readiness from weak evidence.",
            source_ref,
        ))

    # Additional finding codes from vocabulary
    if not config["mutation_evidence_available"]:
        findings.append(_finding(
            "evidence_synthesis_mutation_coverage_missing",
            "Evidence synthesis requires mutation coverage for synthesis.",
            source_ref,
        ))

    if not config["contract_evidence_available"]:
        findings.append(_finding(
            "evidence_synthesis_contract_coverage_missing",
            "Evidence synthesis requires contract coverage for synthesis.",
            source_ref,
        ))

    for es in config["evidence_sources"]:
        if not es.get("sourceRef"):
            findings.append(_finding(
                "evidence_synthesis_source_ref_missing",
                f"Evidence source '{es.get('source_id')}' missing sourceRef.",
                source_ref,
            ))

    for mc in config["mutation_coverage"]:
        if not mc.get("sourceRef"):
            findings.append(_finding(
                "evidence_synthesis_mutation_coverage_missing",
                f"Mutation coverage '{mc.get('mutation_id')}' missing sourceRef.",
                source_ref,
            ))

    for cc in config["contract_coverage"]:
        if not cc.get("sourceRef"):
            findings.append(_finding(
                "evidence_synthesis_contract_coverage_missing",
                f"Contract coverage '{cc.get('contract_id')}' missing sourceRef.",
                source_ref,
            ))

    if config["confidence"] < config["limits"]["confidence_threshold"]:
        findings.append(_finding(
            "evidence_synthesis_weak_evidence_inflation_denied",
            f"Evidence synthesis confidence {config['confidence']} below threshold {config['limits']['confidence_threshold']}.",
            source_ref,
        ))

    return findings


def _finding(code: str, message: str, source_ref: str) -> EvidenceSynthesisFinding:
    return EvidenceSynthesisFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
    )
