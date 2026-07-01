from __future__ import annotations

from pathlib import Path
from typing import Any

SCHEMA_VERSION = "HATE/v1"
TASK_ID = "HATE-MVP-008-P2P3-PRODUCT-READINESS"

def _build_product_readiness_report(
    run_id: str,
    version: str,
    source_refs: list[str],
    aete: dict[str, Any],
    doctor: dict[str, Any],
    alignment: dict[str, Any],
    workflow_acceptance: dict[str, Any],
    product_metrics: dict[str, Any],
    generated_refs: list[str],
    input_gaps: list[dict[str, str]],
) -> dict[str, Any]:
    doctor_findings = int(doctor.get("summary", {}).get("finding_count", 0) or 0)
    unverified_acceptance = int(alignment.get("summary", {}).get("unverified_acceptance_count", 0) or 0)
    overall_status = _product_overall_status(input_gaps, doctor_findings, unverified_acceptance)
    gates = _product_readiness_gates(input_gaps, doctor_findings, unverified_acceptance)
    passed_gate_count = sum(1 for gate in gates if gate["status"] in {"pass", "covered_by_fixture", "covered_by_artifact"})
    evaluation = _build_evaluation_score(
        aete=aete,
        gates=gates,
        generated_refs=generated_refs,
        input_gaps=input_gaps,
        doctor_findings=doctor_findings,
        unverified_acceptance=unverified_acceptance,
        workflow_acceptance=workflow_acceptance,
    )
    unsupported_claims = _product_unsupported_claims(alignment)
    contradictions = _product_contradictions(alignment)
    hard_dqs = _product_hard_dqs(alignment, doctor)
    soft_gaps = _product_soft_gaps(
        input_gaps=input_gaps,
        doctor=doctor,
        alignment=alignment,
        unverified_acceptance=unverified_acceptance,
    )
    canonical_source_refs = _product_source_refs(
        source_refs=source_refs,
        generated_refs=generated_refs,
        alignment=alignment,
        doctor=doctor,
        soft_gaps=soft_gaps,
        hard_dqs=hard_dqs,
        unsupported_claims=unsupported_claims,
        contradictions=contradictions,
    )
    graph_summary = _product_graph_summary(
        alignment=alignment,
        generated_refs=generated_refs,
        gates=gates,
        unsupported_claims=unsupported_claims,
        contradictions=contradictions,
        hard_dqs=hard_dqs,
        soft_gaps=soft_gaps,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "product_readiness_report",
        "run_id": run_id,
        "source_tool": "harness-auto-test-evidence",
        "source_version": version,
        "task_id": TASK_ID,
        "product_readiness_gates": gates,
        "metric_refs": ["enterprise-metrics-report.json"],
        "artifact_refs": generated_refs,
        "evidence_summary": {
            "aete_weighted_score": aete.get("weighted_score"),
            "doctor_findings": doctor_findings,
            "workflow_verdict": workflow_acceptance.get("verdict"),
            "unverified_acceptance_count": unverified_acceptance,
            "missing_input_artifacts": input_gaps,
        },
        "evaluation": evaluation,
        "summary": {
            "overall_status": overall_status,
            "claim_count": graph_summary["claim_count"],
            "unsupported_claim_count": len(unsupported_claims),
            "contradiction_count": len(contradictions),
            "hard_dq_count": len(hard_dqs),
            "soft_gap_count": len(soft_gaps),
            "prg_coverage": f"{passed_gate_count}/7",
            "evaluation_score": evaluation["score"],
            "evaluation_confidence": evaluation["confidence"],
            "go_label_is_advisory": True,
            "metric_count": len(product_metrics.get("metrics", [])),
            "required_artifact_count": len(generated_refs),
            "live_saas_required": False,
            "degraded_by_input_artifacts": bool(input_gaps),
            "degraded_by_doctor_findings": doctor_findings > 0,
            "degraded_by_unverified_acceptance": unverified_acceptance > 0,
        },
        "boundaries": {
            "local_first_precheck_dependency": False,
            "qeg_gate_override": False,
            "release_gate_override": False,
            "publish_gate_override": False,
            "hosted_saas_claim": False,
        },
        "graph_summary": graph_summary,
        "unsupported_claims": unsupported_claims,
        "contradictions": contradictions,
        "hard_dqs": hard_dqs,
        "soft_gaps": soft_gaps,
        "sourceRefs": canonical_source_refs,
        "source_refs": source_refs,
        "release_gate_override": False,
        "publish_gate_override": False,
    }


def _product_graph_summary(
    *,
    alignment: dict[str, Any],
    generated_refs: list[str],
    gates: list[dict[str, Any]],
    unsupported_claims: list[dict[str, Any]],
    contradictions: list[dict[str, Any]],
    hard_dqs: list[dict[str, Any]],
    soft_gaps: list[dict[str, Any]],
) -> dict[str, Any]:
    summary = alignment.get("summary", {}) if isinstance(alignment.get("summary"), dict) else {}
    claim_count = _safe_int(
        summary.get("claim_count"),
        _safe_int(summary.get("acceptance_count"), _safe_int(summary.get("requirement_count"), 0)),
    )
    return {
        "claim_count": claim_count,
        "requirement_count": _safe_int(summary.get("requirement_count"), claim_count),
        "acceptance_count": _safe_int(summary.get("acceptance_count"), claim_count),
        "generated_artifact_count": len(set(generated_refs)),
        "readiness_gate_count": len(gates),
        "unsupported_claim_count": len(unsupported_claims),
        "contradiction_count": len(contradictions),
        "hard_dq_count": len(hard_dqs),
        "soft_gap_count": len(soft_gaps),
        "source_report_refs": ["requirement-evidence-alignment.json", "doctor-report.json", "product-readiness-report.json"],
    }


def _product_unsupported_claims(alignment: dict[str, Any]) -> list[dict[str, Any]]:
    claims = alignment.get("unsupported_claims")
    if isinstance(claims, list):
        return [_canonical_gap_item(item, "unsupported_claim", "unsupported_claim") for item in claims if isinstance(item, dict)]

    result: list[dict[str, Any]] = []
    for key in ("claims", "acceptance_items", "requirements"):
        for item in alignment.get(key, []) if isinstance(alignment.get(key), list) else []:
            if not isinstance(item, dict):
                continue
            status = str(item.get("status") or item.get("support_status") or item.get("evidence_status") or "")
            if status in {"unsupported", "missing_evidence", "unverified"}:
                result.append(_canonical_gap_item(item, str(item.get("claim_id") or item.get("id") or key), "unsupported_claim"))
    return result


def _product_contradictions(alignment: dict[str, Any]) -> list[dict[str, Any]]:
    contradictions = alignment.get("contradictions")
    if isinstance(contradictions, list):
        return [_canonical_gap_item(item, "contradiction", "contradiction") for item in contradictions if isinstance(item, dict)]
    return []


def _product_hard_dqs(alignment: dict[str, Any], doctor: dict[str, Any]) -> list[dict[str, Any]]:
    hard_dqs: list[dict[str, Any]] = []
    for source in (alignment.get("hard_dqs"), doctor.get("hard_dqs")):
        if isinstance(source, list):
            hard_dqs.extend(_canonical_gap_item(item, "hard_dq", "hard_dq") for item in source if isinstance(item, dict))
    for finding in doctor.get("findings", []) if isinstance(doctor.get("findings"), list) else []:
        if isinstance(finding, dict) and str(finding.get("severity") or finding.get("effect") or "") in {"hard", "hard_dq", "block", "critical"}:
            hard_dqs.append(_canonical_gap_item(finding, str(finding.get("code") or "doctor_hard_dq"), "hard_dq"))
    return hard_dqs


def _product_soft_gaps(
    *,
    input_gaps: list[dict[str, str]],
    doctor: dict[str, Any],
    alignment: dict[str, Any],
    unverified_acceptance: int,
) -> list[dict[str, Any]]:
    soft_gaps: list[dict[str, Any]] = []
    for gap in input_gaps:
        artifact_ref = str(gap.get("artifact_ref", "missing-input"))
        soft_gaps.append(
            {
                "code": "missing_input_artifact",
                "severity": "medium",
                "message": str(gap.get("reason") or "expected input artifact missing"),
                "artifact_ref": artifact_ref,
                "root": str(gap.get("root") or "unknown"),
                "readiness_effect": "hold",
                "sourceRefs": [artifact_ref],
            }
        )
    for finding in doctor.get("findings", []) if isinstance(doctor.get("findings"), list) else []:
        if isinstance(finding, dict) and str(finding.get("severity") or finding.get("effect") or "") not in {"hard", "hard_dq", "block", "critical"}:
            soft_gaps.append(_canonical_gap_item(finding, str(finding.get("code") or "doctor_finding"), "soft_gap"))
    if unverified_acceptance and not any(gap.get("code") == "unverified_acceptance" for gap in soft_gaps):
        soft_gaps.append(
            {
                "code": "unverified_acceptance",
                "severity": "medium",
                "message": f"{unverified_acceptance} acceptance items are not verified by evidence.",
                "readiness_effect": "conditional",
                "sourceRefs": _extract_source_refs(alignment) or ["requirement-evidence-alignment.json"],
            }
        )
    return soft_gaps


def _canonical_gap_item(item: dict[str, Any], default_code: str, default_kind: str) -> dict[str, Any]:
    source_refs = _extract_source_refs(item)
    return {
        "code": str(item.get("code") or item.get("finding_code") or item.get("claim_id") or item.get("id") or default_code),
        "kind": str(item.get("kind") or item.get("type") or default_kind),
        "severity": str(item.get("severity") or "medium"),
        "message": str(item.get("message") or item.get("reason") or default_code),
        "readiness_effect": str(item.get("readiness_effect") or item.get("effect") or "hold"),
        "sourceRefs": source_refs,
    }


def _product_source_refs(
    *,
    source_refs: list[str],
    generated_refs: list[str],
    alignment: dict[str, Any],
    doctor: dict[str, Any],
    soft_gaps: list[dict[str, Any]],
    hard_dqs: list[dict[str, Any]],
    unsupported_claims: list[dict[str, Any]],
    contradictions: list[dict[str, Any]],
) -> list[str]:
    refs = list(source_refs) + list(generated_refs)
    refs.extend(_extract_source_refs(alignment))
    refs.extend(_extract_source_refs(doctor))
    for item in soft_gaps + hard_dqs + unsupported_claims + contradictions:
        refs.extend(_extract_source_refs(item))
    return sorted({str(ref) for ref in refs if str(ref)})


def _extract_source_refs(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return []
    refs: list[str] = []
    for key in ("sourceRefs", "source_refs"):
        raw = value.get(key)
        if isinstance(raw, list):
            refs.extend(str(ref) for ref in raw if str(ref))
        elif isinstance(raw, str) and raw:
            refs.append(raw)
    raw_ref = value.get("sourceRef") or value.get("source_ref")
    if isinstance(raw_ref, str) and raw_ref:
        refs.append(raw_ref)
    return sorted(set(refs))


def _build_evaluation_score(
    *,
    aete: dict[str, Any],
    gates: list[dict[str, Any]],
    generated_refs: list[str],
    input_gaps: list[dict[str, str]],
    doctor_findings: int,
    unverified_acceptance: int,
    workflow_acceptance: dict[str, Any],
) -> dict[str, Any]:
    """Build a gate-capped product readiness score.

    The score is advisory and intentionally separate from release approval.
    Positive evidence explains the raw score, but unresolved gates cap the final
    score so missing inputs or unverified acceptance cannot be hidden by broad
    artifact generation.
    """
    aete_weighted = _safe_float(aete.get("weighted_score"), 0.0)
    passed_gate_count = sum(1 for gate in gates if gate["status"] in {"pass", "covered_by_fixture", "covered_by_artifact"})
    required_artifacts = len(_product_artifact_refs())
    generated_ratio = min(1.0, len(set(generated_refs)) / required_artifacts) if required_artifacts else 0.0
    workflow_verdict = str(workflow_acceptance.get("verdict", ""))
    calibration_status = str(aete.get("calibration_status", "unknown"))
    score_confidence = str(aete.get("score_confidence", "unknown"))

    additions = [
        _score_component("aete_weighted_score", round(aete_weighted * 50, 2), 50, "AETE weighted score is the primary evidence quality signal."),
        _score_component("product_readiness_gate_coverage", round((passed_gate_count / 7) * 20, 2), 20, f"{passed_gate_count}/7 PRG gates have positive evidence status."),
        _score_component("required_artifact_completeness", round(generated_ratio * 15, 2), 15, f"{len(set(generated_refs))}/{required_artifacts} required product artifacts generated."),
        _score_component(
            "workflow_acceptance",
            10 if workflow_verdict == "accepted" else 6 if workflow_verdict == "accepted_with_gaps" else 0,
            10,
            f"Workflow acceptance verdict is {workflow_verdict or 'missing'}.",
        ),
        _score_component("doctor_hygiene", 5 if doctor_findings == 0 else 0, 5, f"Doctor finding count is {doctor_findings}."),
    ]
    penalties = [
        _score_penalty("missing_input_artifacts", min(40, len(input_gaps) * 10), f"{len(input_gaps)} required upstream artifacts are missing."),
        _score_penalty("doctor_findings", min(25, doctor_findings * 5), f"{doctor_findings} doctor findings remain."),
        _score_penalty("unverified_acceptance", min(35, unverified_acceptance * 7), f"{unverified_acceptance} acceptance items are unverified."),
        _score_penalty(
            "uncalibrated_aete",
            5 if calibration_status != "calibrated" else 0,
            f"AETE calibration status is {calibration_status}.",
        ),
        _score_penalty(
            "score_confidence",
            10 if score_confidence == "low" else 5 if score_confidence in {"medium", "unknown", ""} else 0,
            f"AETE score confidence is {score_confidence or 'unknown'}.",
        ),
    ]
    addition_total = round(sum(item["points"] for item in additions), 2)
    penalty_total = round(sum(item["points"] for item in penalties), 2)
    raw_score = round(max(0.0, min(100.0, addition_total - penalty_total)), 2)
    caps = _evaluation_score_caps(
        input_gaps=input_gaps,
        doctor_findings=doctor_findings,
        unverified_acceptance=unverified_acceptance,
        workflow_verdict=workflow_verdict,
        calibration_status=calibration_status,
        score_confidence=score_confidence,
    )
    cap_score = min((cap["max_score"] for cap in caps), default=100)
    score = round(min(raw_score, cap_score), 2)
    return {
        "score": score,
        "max_score": 100,
        "method": "gate_capped_evidence_score_v2",
        "confidence": _evaluation_confidence(score_confidence, calibration_status, input_gaps, doctor_findings, unverified_acceptance),
        "go_label_is_advisory": True,
        "release_approval": False,
        "raw_score": raw_score,
        "cap_score": cap_score,
        "caps": caps,
        "addition_total": addition_total,
        "penalty_total": penalty_total,
        "additions": additions,
        "penalties": penalties,
        "interpretation": _evaluation_interpretation(score),
    }


def _score_component(component_id: str, points: float, max_points: float, reason: str) -> dict[str, Any]:
    return {
        "component_id": component_id,
        "points": round(points, 2),
        "max_points": max_points,
        "reason": reason,
    }


def _score_penalty(component_id: str, points: float, reason: str) -> dict[str, Any]:
    return {
        "component_id": component_id,
        "points": round(points, 2),
        "reason": reason,
    }


def _evaluation_score_caps(
    *,
    input_gaps: list[dict[str, str]],
    doctor_findings: int,
    unverified_acceptance: int,
    workflow_verdict: str,
    calibration_status: str,
    score_confidence: str,
) -> list[dict[str, Any]]:
    caps: list[dict[str, Any]] = []
    if input_gaps:
        caps.append(_score_cap(
            "missing_input_artifacts",
            49,
            "Missing upstream artifacts prevent readiness from exceeding not-ready evidence.",
        ))
    if doctor_findings:
        caps.append(_score_cap(
            "doctor_findings_present",
            69,
            "Unresolved doctor findings prevent usable-with-review scoring.",
        ))
    if unverified_acceptance:
        caps.append(_score_cap(
            "unverified_acceptance_present",
            69,
            "Unverified acceptance prevents usable-with-review scoring.",
        ))
    if workflow_verdict == "accepted_with_gaps":
        caps.append(_score_cap(
            "workflow_accepted_with_gaps",
            74,
            "Workflow acceptance with gaps cannot score as strong evidence.",
        ))
    elif workflow_verdict not in {"accepted", ""}:
        caps.append(_score_cap(
            "workflow_not_accepted",
            59,
            f"Workflow acceptance verdict is {workflow_verdict}.",
        ))
    if calibration_status != "calibrated":
        caps.append(_score_cap(
            "uncalibrated_aete",
            79,
            "Uncalibrated AETE cannot score as strong advisory evidence.",
        ))
    if score_confidence == "low":
        caps.append(_score_cap(
            "low_score_confidence",
            59,
            "Low AETE score confidence caps readiness below material acceptance.",
        ))
    elif score_confidence in {"medium", "unknown", ""}:
        caps.append(_score_cap(
            "non_high_score_confidence",
            84,
            f"AETE score confidence is {score_confidence or 'unknown'}.",
        ))
    return caps


def _score_cap(cap_id: str, max_score: float, reason: str) -> dict[str, Any]:
    return {
        "cap_id": cap_id,
        "max_score": max_score,
        "reason": reason,
    }


def _evaluation_confidence(
    score_confidence: str,
    calibration_status: str,
    input_gaps: list[dict[str, str]],
    doctor_findings: int,
    unverified_acceptance: int,
) -> str:
    if input_gaps or doctor_findings or unverified_acceptance:
        return "medium"
    if calibration_status != "calibrated":
        return "medium" if score_confidence == "high" else "low"
    return score_confidence if score_confidence in {"high", "medium", "low"} else "medium"


def _evaluation_interpretation(score: float) -> str:
    if score >= 85:
        return "strong_advisory_evidence"
    if score >= 70:
        return "usable_with_review"
    if score >= 50:
        return "material_gaps"
    return "not_ready"


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _missing_product_input_refs(trust_dir: Path, workflow_dir: Path) -> list[dict[str, str]]:
    expected = {
        trust_dir: [
            "aete-score.json",
            "artifact-resolver-map.json",
            "doctor-report.json",
            "adapter-capability-manifest.json",
            "adapter-conformance-report.json",
            "canonical-identity-index.json",
            "retry-aggregation.json",
            "trust-summary.md",
        ],
        workflow_dir: [
            "requirement-evidence-alignment.json",
            "workflow-task-seed.json",
            "workflow-acceptance-record.json",
            "workflow-evidence.jsonl",
            "workflow-docs-stale.json",
            "workflow-birdseye-map.json",
            "shipyard-run-evidence.json",
        ],
    }
    gaps: list[dict[str, str]] = []
    for base, names in expected.items():
        root = "trust" if base == trust_dir else "workflow"
        for name in names:
            if not (base / name).exists():
                gaps.append({"root": root, "artifact_ref": name, "reason": "expected input artifact missing"})
    return gaps


def _product_overall_status(input_gaps: list[dict[str, str]], doctor_findings: int, unverified_acceptance: int) -> str:
    if input_gaps:
        return "hold"
    if doctor_findings or unverified_acceptance:
        return "conditional"
    return "go"


def _product_readiness_gates(
    input_gaps: list[dict[str, str]],
    doctor_findings: int,
    unverified_acceptance: int,
) -> list[dict[str, Any]]:
    prg2_status = "hold" if any(gap["root"] == "trust" for gap in input_gaps) else "covered_by_fixture"
    prg3_status = "hold" if input_gaps else "conditional" if doctor_findings or unverified_acceptance else "covered_by_fixture"
    prg4_status = "hold" if any(gap["root"] == "workflow" for gap in input_gaps) else "covered_by_artifact"
    return [
        _gate("PRG-0", "Prototype", "pass", ["P0a golden fixture is executable."]),
        _gate("PRG-1", "Internal Alpha", "covered_by_fixture", ["P0b QEG export fixture is executable."]),
        _gate("PRG-2", "Private Beta", prg2_status, ["Adapter conformance report is generated."]),
        _gate("PRG-3", "Team GA", prg3_status, ["QEG export, doctor, summary, and docs evidence are linked."]),
        _gate("PRG-4", "Enterprise Ready", prg4_status, ["RBAC/read model/support/customer docs artifacts are present."]),
        _gate("PRG-5", "Regulated Ready", "covered_by_artifact" if not input_gaps else "hold", ["Trust, privacy, audit, and assurance artifacts are present."]),
        _gate("PRG-6", "Enterprise Product Ready", "covered_by_artifact" if not input_gaps else "hold", ["Enterprise metrics and governance reports are present."]),
    ]


def _gate(gate_id: str, name: str, status: str, evidence: list[str]) -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "name": name,
        "status": status,
        "evidence_refs": evidence,
        "source_refs": ["product-readiness-report.json"],
    }


def _build_product_metrics(
    run_id: str,
    aete: dict[str, Any],
    doctor: dict[str, Any],
    conformance: dict[str, Any],
    alignment: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "product_metrics_report",
        "run_id": run_id,
        "metrics": [
            {"metric_id": "time_to_first_evidence", "value": "fixture_reproducible", "source_refs": ["P0A_GOLDEN_PATH.md"]},
            {"metric_id": "evidence_eligibility_rate", "value": "tracked", "source_refs": ["qeg-export-report.json"]},
            {"metric_id": "high_risk_evidence_coverage", "value": "partial", "source_refs": ["requirement-evidence-alignment.json"]},
            {"metric_id": "adapter_conformance_rate", "value": conformance.get("summary", {}).get("overall_status"), "source_refs": ["adapter-conformance-report.json"]},
            {"metric_id": "trust_score", "value": aete.get("weighted_score"), "source_refs": ["aete-score.json"]},
            {"metric_id": "doctor_finding_count", "value": doctor.get("summary", {}).get("finding_count"), "source_refs": ["doctor-report.json"]},
            {"metric_id": "unverified_acceptance_count", "value": alignment.get("summary", {}).get("unverified_acceptance_count"), "source_refs": ["requirement-evidence-alignment.json"]},
        ],
        "privacy_boundary": {
            "contains_customer_code": False,
            "contains_raw_artifact": False,
            "contains_secret": False,
            "contains_pii": False,
        },
        "release_gate_override": False,
        "publish_gate_override": False,
    }


def _product_artifact_refs() -> list[str]:
    return [
        "dashboard-report.html",
        "dashboard-view-model.json",
        "pr-annotation-export.json",
        "artifact-budget-report.json",
        "attestation-report.json",
        "external-export-report.json",
        "product-error-catalog.json",
        "enterprise-risk-debt-register.json",
        "privacy-quarantine-report.json",
        "hosted-read-model-index.json",
        "domain-model-report.json",
        "rbac-matrix-report.json",
        "identity-connector-report.json",
        "enterprise-connector-report.json",
        "audit-event-log.json",
        "retention-governance-report.json",
        "release-migration-report.json",
        "entitlement-usage-report.json",
        "enterprise-metrics-report.json",
        "customer-docs-index.json",
        "incident-slo-report.json",
        "adoption-health-report.json",
        "security-trust-packet.json",
        "residency-deployment-report.json",
        "roadmap-decision-record.json",
        "accessibility-localization-report.json",
        "commercial-contract-report.json",
        "audit-assurance-pack.json",
        "support-diagnostic-bundle.json",
        "privacy-telemetry-report.json",
        "governance-portfolio-report.json",
        "release-candidate-pack.json",
    ]
