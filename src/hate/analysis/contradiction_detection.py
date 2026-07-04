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
    diagnostics = _derive_diagnostics(config, source_refs[0])
    findings = _findings_for(config, diagnostics, source_refs[0])
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
            "evidence_record_count": len(config["evidence_records"]),
            "derived_contradiction_count": len(diagnostics["derived_contradictions"]),
            "blocked_claim_reference_count": len(diagnostics["blocked_claim_refs"]),
            "duplicate_contradiction_count": len(diagnostics["duplicate_contradiction_ids"]),
            "confidence": config["confidence"],
            "finding_count": len(findings),
        },
        "contradictions": config["contradictions"],
        "blocking_effects": config["blocking_effects"],
        "claim_impacts": config["claim_impacts"],
        "evidence_records": config["evidence_records"],
        "release_claims": config["release_claims"],
        "contradiction_diagnostics": diagnostics,
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
    evidence_records = [
        _normalize_evidence_record(e)
        for e in config.get("evidence_records", [])
        if isinstance(e, dict)
    ]
    release_claims = [
        _normalize_release_claim(c)
        for c in config.get("release_claims", [])
        if isinstance(c, dict)
    ]
    return {
        "contradictions": contradictions,
        "blocking_effects": blocking_effects,
        "claim_impacts": claim_impacts,
        "evidence_records": evidence_records,
        "release_claims": release_claims,
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


def _normalize_evidence_record(e: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_id": str(e.get("record_id", "") or ""),
        "record_type": str(e.get("record_type", "") or ""),
        "status": str(e.get("status", "") or ""),
        "readiness_effect": str(e.get("readiness_effect", "") or ""),
        "severity": str(e.get("severity", "") or ""),
        "finding_code": str(e.get("finding_code", "") or ""),
        "requirement_ref": str(e.get("requirement_ref", "") or ""),
        "claim_id": str(e.get("claim_id", "") or ""),
        "metric_type": str(e.get("metric_type", "") or ""),
        "current_value": _optional_float(e.get("current_value")),
        "baseline_value": _optional_float(e.get("baseline_value")),
        "schema_version": str(e.get("schema_version", "") or ""),
        "expected_schema_version": str(e.get("expected_schema_version", "") or ""),
        "sourceRef": str(e.get("sourceRef", "") or ""),
    }


def _normalize_release_claim(c: dict[str, Any]) -> dict[str, Any]:
    return {
        "claim_id": str(c.get("claim_id", "") or ""),
        "status": str(c.get("status", "") or ""),
        "evidence_refs": [str(ref) for ref in c.get("evidence_refs", []) if str(ref)],
        "sourceRef": str(c.get("sourceRef", "") or ""),
    }


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_limits(limits: dict[str, Any]) -> dict[str, Any]:
    return {
        "confidence_threshold": float(limits.get("confidence_threshold", 0.7) or 0.7),
        "max_contradictions": int(limits.get("max_contradictions", 50) or 50),
        "max_blocking_effects": int(limits.get("max_blocking_effects", 20) or 20),
        "max_claim_impacts": int(limits.get("max_claim_impacts", 50) or 50),
    }


def _derive_diagnostics(config: dict[str, Any], default_source_ref: str) -> dict[str, Any]:
    contradiction_ids = [c["contradiction_id"] for c in config["contradictions"] if c["contradiction_id"]]
    duplicate_ids = _duplicates(contradiction_ids)
    derived = []

    for evidence in config["evidence_records"]:
        if evidence["status"] == "pass" and evidence["severity"] == "critical":
            derived.append(_derived("pass_with_critical", evidence["record_id"], evidence["sourceRef"]))
        if evidence["status"] == "pass" and evidence["readiness_effect"] in {"hold", "blocked"}:
            derived.append(_derived("pass_with_nonpass_readiness", evidence["record_id"], evidence["sourceRef"]))
        if (
            evidence["record_type"] in {"contract", "schema", "contract_check"}
            and evidence["schema_version"]
            and evidence["expected_schema_version"]
            and evidence["schema_version"] != evidence["expected_schema_version"]
        ):
            derived.append(_derived("contract_schema_conflict", evidence["record_id"], evidence["sourceRef"]))

    metrics = _metrics_by_requirement(config["evidence_records"])
    for requirement_ref, values in metrics.items():
        coverage = values.get("coverage")
        mutation = values.get("mutation")
        if coverage and mutation and coverage["current"] > coverage["baseline"] and mutation["current"] < mutation["baseline"]:
            derived.append(_derived("coverage_up_mutation_down", requirement_ref, coverage["sourceRef"] or mutation["sourceRef"]))

    blocked_evidence = {
        e["record_id"]
        for e in config["evidence_records"]
        if e["readiness_effect"] == "blocked" or e["status"] == "blocked" or e["severity"] == "critical"
    }
    blocked_claim_refs = sorted({
        claim["claim_id"]
        for claim in config["release_claims"]
        if claim["status"] in {"pass", "ready", "accepted"} and any(ref in blocked_evidence for ref in claim["evidence_refs"])
    })
    for claim_id in blocked_claim_refs:
        derived.append(_derived("release_claim_uses_blocked_evidence", claim_id, source_ref=default_source_ref))

    missing_source_refs = sorted(
        item_id
        for item_id, ref in [
            *[(c["contradiction_id"], c["sourceRef"]) for c in config["contradictions"]],
            *[(b["effect_id"], b["sourceRef"]) for b in config["blocking_effects"]],
            *[(i["claim_id"], i["sourceRef"]) for i in config["claim_impacts"]],
        ]
        if item_id and not ref
    )
    return {
        "derived_contradictions": derived,
        "blocked_claim_refs": blocked_claim_refs,
        "duplicate_contradiction_ids": sorted(duplicate_ids),
        "missing_source_ref_ids": missing_source_refs,
    }


def _duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return duplicates


def _derived(contradiction_type: str, subject_ref: str, source_ref: str) -> dict[str, str]:
    return {
        "contradiction_type": contradiction_type,
        "subject_ref": subject_ref,
        "sourceRef": source_ref,
    }


def _metrics_by_requirement(records: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    grouped: dict[str, dict[str, dict[str, Any]]] = {}
    for record in records:
        if record["metric_type"] not in {"coverage", "mutation"}:
            continue
        if record["current_value"] is None or record["baseline_value"] is None:
            continue
        requirement_ref = record["requirement_ref"] or "_global"
        grouped.setdefault(requirement_ref, {})[record["metric_type"]] = {
            "current": record["current_value"],
            "baseline": record["baseline_value"],
            "sourceRef": record["sourceRef"],
        }
    return grouped


def _findings_for(
    config: dict[str, Any],
    diagnostics: dict[str, Any],
    source_ref: str,
) -> list[ContradictionFinding]:
    findings: list[ContradictionFinding] = []

    # HATE-GAP-056 primary negative: pass with critical finding blocked
    if config.get("pass_status_with_critical") and config.get("critical_finding_present"):
        findings.append(_finding(
            "contradiction_pass_with_critical_finding_blocked",
            "Pass status contradicts critical finding presence.",
            source_ref,
            readiness_effect="blocked",
        ))

    derived_types = {d["contradiction_type"] for d in diagnostics["derived_contradictions"]}
    if "pass_with_critical" in derived_types or "pass_with_nonpass_readiness" in derived_types:
        findings.append(_finding(
            "contradiction_pass_with_critical_finding_blocked",
            "Evidence records contain pass status with critical or non-pass readiness signal.",
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

    if "coverage_up_mutation_down" in derived_types:
        findings.append(_finding(
            "contradiction_coverage_up_mutation_down",
            "Coverage improved while mutation score regressed for the same requirement.",
            source_ref,
        ))

    # Contract schema alignment check
    if not config.get("contract_schema_aligned"):
        findings.append(_finding(
            "contradiction_contract_schema_conflict",
            "Contract schema alignment violated.",
            source_ref,
        ))

    if "contract_schema_conflict" in derived_types:
        findings.append(_finding(
            "contradiction_contract_schema_conflict",
            "Contract/schema evidence versions conflict.",
            source_ref,
        ))

    if "release_claim_uses_blocked_evidence" in derived_types:
        findings.append(_finding(
            "contradiction_release_claim_uses_blocked_evidence",
            "Release claim is marked ready while linked evidence is blocked or critical.",
            source_ref,
            readiness_effect="blocked",
        ))

    if diagnostics["duplicate_contradiction_ids"]:
        findings.append(_finding(
            "contradiction_duplicate_id",
            f"Duplicate contradiction ids detected: {', '.join(diagnostics['duplicate_contradiction_ids'])}.",
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

    for missing_id in diagnostics["missing_source_ref_ids"]:
        if not any(missing_id == c.get("contradiction_id") for c in config["contradictions"]):
            findings.append(_finding(
                "contradiction_missing_source_ref",
                f"Contradiction related item '{missing_id}' missing sourceRef.",
                source_ref,
            ))

    if len(config["contradictions"]) > config["limits"]["max_contradictions"]:
        findings.append(_finding(
            "contradiction_budget_exceeded",
            f"Contradiction count {len(config['contradictions'])} exceeds limit {config['limits']['max_contradictions']}.",
            source_ref,
        ))

    if len(config["blocking_effects"]) > config["limits"]["max_blocking_effects"]:
        findings.append(_finding(
            "contradiction_blocking_effect_budget_exceeded",
            f"Blocking effect count {len(config['blocking_effects'])} exceeds limit {config['limits']['max_blocking_effects']}.",
            source_ref,
        ))

    if len(config["claim_impacts"]) > config["limits"]["max_claim_impacts"]:
        findings.append(_finding(
            "contradiction_claim_impact_budget_exceeded",
            f"Claim impact count {len(config['claim_impacts'])} exceeds limit {config['limits']['max_claim_impacts']}.",
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
