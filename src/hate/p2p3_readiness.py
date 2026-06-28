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
        "summary": {
            "overall_status": overall_status,
            "prg_coverage": f"{passed_gate_count}/7",
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
        "source_refs": source_refs,
        "release_gate_override": False,
        "publish_gate_override": False,
    }


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


