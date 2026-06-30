"""Policy simulation evaluation for HATE-GAP-028."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PolicySimulationFinding:
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


def evaluate_policy_simulation_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_policy_simulation_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "policy-simulation-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_policy_simulation_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "policy-simulation-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["policy-simulation"])
    simulation_config = _normalize_simulation_config(input_data.get("simulation_config", input_data))
    findings = _findings_for(simulation_config, source_refs[0])
    status = "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": "policy-simulation-report",
        "report_id": report_id,
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "simulation_config": simulation_config,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "dry_run_supported": simulation_config["dry_run_supported"],
            "blast_radius_bounded": simulation_config["blast_radius_bounded"],
            "rollback_plan_defined": simulation_config["rollback_plan_defined"],
            "affected_repo_count": len(simulation_config["affected_repos"]),
            "finding_count": len(findings),
        },
        "sourceRefs": sorted(set(source_refs)),
    }


def _normalize_simulation_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw_config or {})
    affected_repos = [str(repo) for repo in config.get("affected_repos", []) if str(repo)]
    return {
        "dry_run_supported": bool(config.get("dry_run_supported", False)),
        "blast_radius_bounded": bool(config.get("blast_radius_bounded", False)),
        "rollback_plan_defined": bool(config.get("rollback_plan_defined", False)),
        "evidence_eligibility_impact_shown": bool(config.get("evidence_eligibility_impact_shown", False)),
        "audit_evidence_generated": bool(config.get("audit_evidence_generated", False)),
        "affected_repos": affected_repos,
        "change_type": str(config.get("change_type") or ""),
        "max_affected_threshold": int(config.get("max_affected_threshold", 0) or 0),
    }


def _findings_for(config: dict[str, Any], source_ref: str) -> list[PolicySimulationFinding]:
    findings: list[PolicySimulationFinding] = []
    if not config["dry_run_supported"]:
        findings.append(_finding(
            "policy_simulation_dry_run_missing",
            "Policy simulation requires dry-run diff support.",
            source_ref,
        ))
    if not config["blast_radius_bounded"]:
        findings.append(_finding(
            "policy_simulation_blast_radius_unbounded",
            "Policy simulation blast radius must be bounded with max affected threshold.",
            source_ref,
        ))
    if not config["rollback_plan_defined"]:
        findings.append(_finding(
            "policy_simulation_rollback_missing",
            "Policy simulation requires rollback plan evidence.",
            source_ref,
        ))
    if not config["evidence_eligibility_impact_shown"]:
        findings.append(_finding(
            "policy_simulation_eligibility_impact_missing",
            "Policy simulation must show evidence eligibility impact.",
            source_ref,
        ))
    if not config["audit_evidence_generated"]:
        findings.append(_finding(
            "policy_simulation_audit_evidence_missing",
            "Policy simulation must generate audit evidence.",
            source_ref,
        ))
    if config["affected_repos"] and config["max_affected_threshold"] > 0:
        if len(config["affected_repos"]) > config["max_affected_threshold"]:
            findings.append(_finding(
                "policy_simulation_blast_radius_exceeded",
                "Affected repo count exceeds blast radius threshold.",
                source_ref,
            ))
    return findings


def _finding(code: str, message: str, source_ref: str) -> PolicySimulationFinding:
    return PolicySimulationFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
    )