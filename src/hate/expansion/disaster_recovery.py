"""Disaster recovery evaluation for HATE-GAP-037."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DisasterRecoveryFinding:
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


def evaluate_disaster_recovery_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_disaster_recovery_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "disaster-recovery-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_disaster_recovery_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "disaster-recovery-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["disaster-recovery"])
    dr_config = _normalize_dr_config(input_data.get("dr_config", input_data))
    findings = _findings_for(dr_config, source_refs[0])
    status = "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": "disaster-recovery-report",
        "report_id": report_id,
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "dr_config": dr_config,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "backup_inventory_present": dr_config["backup_inventory_present"],
            "restore_drill_executed": dr_config["restore_drill_executed"],
            "restore_verified": dr_config["restore_verified"],
            "rpo_within_budget": dr_config["rpo_minutes"] <= dr_config["rpo_budget_minutes"],
            "rto_within_budget": dr_config["rto_minutes"] <= dr_config["rto_budget_minutes"],
            "corrupt_backup_detected": dr_config["corrupt_backup_detected"],
            "incident_evidence_present": dr_config["incident_evidence_present"],
            "finding_count": len(findings),
        },
        "sourceRefs": sorted(set(source_refs)),
    }


def _normalize_dr_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw_config or {})
    return {
        "backup_inventory_present": bool(config.get("backup_inventory_present", False)),
        "backup_id": str(config.get("backup_id") or ""),
        "backup_created_at": str(config.get("backup_created_at") or ""),
        "backup_integrity_hash": str(config.get("backup_integrity_hash") or ""),
        "restore_drill_executed": bool(config.get("restore_drill_executed", False)),
        "restore_verified": bool(config.get("restore_verified", False)),
        "rpo_minutes": int(config.get("rpo_minutes", 0) or 0),
        "rto_minutes": int(config.get("rto_minutes", 0) or 0),
        "rpo_budget_minutes": int(config.get("rpo_budget_minutes", 0) or 0),
        "rto_budget_minutes": int(config.get("rto_budget_minutes", 0) or 0),
        "corrupt_backup_detected": bool(config.get("corrupt_backup_detected", False)),
        "incident_evidence_present": bool(config.get("incident_evidence_present", False)),
    }


def _findings_for(config: dict[str, Any], source_ref: str) -> list[DisasterRecoveryFinding]:
    findings: list[DisasterRecoveryFinding] = []
    if not config["backup_inventory_present"]:
        findings.append(_finding(
            "disaster_recovery_backup_inventory_missing",
            "Disaster recovery requires backup inventory.",
            source_ref,
        ))
    if not config["restore_drill_executed"]:
        findings.append(_finding(
            "disaster_recovery_restore_drill_missing",
            "Disaster recovery requires restore drill execution.",
            source_ref,
        ))
    if not config["restore_verified"]:
        findings.append(_finding(
            "disaster_recovery_restore_verification_missing",
            "Disaster recovery requires restore verification.",
            source_ref,
        ))
    if config["rpo_minutes"] > config["rpo_budget_minutes"]:
        findings.append(_finding(
            "disaster_recovery_rpo_exceeded",
            f"RPO {config['rpo_minutes']} minutes exceeds budget {config['rpo_budget_minutes']} minutes.",
            source_ref,
        ))
    if config["rto_minutes"] > config["rto_budget_minutes"]:
        findings.append(_finding(
            "disaster_recovery_rto_exceeded",
            f"RTO {config['rto_minutes']} minutes exceeds budget {config['rto_budget_minutes']} minutes.",
            source_ref,
        ))
    if config["corrupt_backup_detected"]:
        findings.append(_finding(
            "disaster_recovery_corrupt_backup_denied",
            "Corrupt backup detected is denied by disaster recovery policy.",
            source_ref,
        ))
    if not config["backup_integrity_hash"]:
        findings.append(_finding(
            "disaster_recovery_integrity_hash_missing",
            "Disaster recovery requires backup integrity hash.",
            source_ref,
        ))
    if not config["incident_evidence_present"]:
        findings.append(_finding(
            "disaster_recovery_incident_evidence_missing",
            "Disaster recovery requires incident evidence.",
            source_ref,
        ))
    return findings


def _finding(code: str, message: str, source_ref: str) -> DisasterRecoveryFinding:
    return DisasterRecoveryFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
    )