from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .common import apply_productization_contract_tree, productization_envelope


@dataclass(frozen=True)
class StoreDrFinding:
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


def evaluate_store_dr_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    report = build_store_dr_report(
        payload.get("input", {}),
        report_id=str(payload.get("fixture_id") or "store-dr-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_store_dr_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "store-dr-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["store-dr"])
    operation = _normalize_operation(input_data.get("operation", input_data))
    backup_operation = _backup_operation(operation)
    restore_operation = _restore_operation(operation)
    drill_result = _drill_result(operation)
    findings = _findings_for(operation, source_refs[0])
    status = "hold" if findings else "pass"
    report = {
        "schema_version": "HATE/v1",
        "record_type": "store-dr-report",
        "report_id": report_id,
        **productization_envelope(input_data, report_id=report_id, source_refs=source_refs),
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "backup_operation": backup_operation,
        "restore_operation": restore_operation,
        "dr_drill_result": drill_result,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "backup_id": operation["backup_id"],
            "corruption_scan_result": operation["corruption_scan_result"],
            "projection_rebuild_status": operation["projection_rebuild_status"],
            "legal_hold_preserved": operation["legal_hold_count_after"] >= operation["legal_hold_count_before"],
            "rto_budget_status": "exceeded"
            if operation["rto_budget_seconds"] >= 0 and operation["rto_seconds"] > operation["rto_budget_seconds"]
            else "within_budget",
            "rpo_budget_status": "exceeded"
            if operation["rpo_budget_seconds"] >= 0 and operation["rpo_seconds"] > operation["rpo_budget_seconds"]
            else "within_budget",
            "finding_count": len(findings),
        },
        "sourceRefs": sorted(set(source_refs)),
    }
    return apply_productization_contract_tree(report, source_refs=source_refs)


def build_store_dr_runbook(
    input_data: dict[str, Any],
    *,
    runbook_id: str = "store-dr-runbook",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["store-dr-runbook"])
    report = (
        input_data
        if input_data.get("record_type") == "store-dr-report"
        else build_store_dr_report(input_data, report_id=f"{runbook_id}:report", source_refs=source_refs)
    )
    backup = dict(report.get("backup_operation", {}))
    restore = dict(report.get("restore_operation", {}))
    drill = dict(report.get("dr_drill_result", {}))
    steps = _runbook_steps_for(backup, restore, drill, report.get("summary", {}), source_refs[0])
    findings = _runbook_findings(report, steps, source_refs[0])
    runbook = {
        "schema_version": "HATE/v1",
        "record_type": "store-dr-runbook",
        "runbook_id": runbook_id,
        **productization_envelope(input_data, report_id=runbook_id, source_refs=source_refs),
        "readiness_effect": "hold" if findings else "none",
        "backup_id": backup.get("backup_id", ""),
        "restore_status": restore.get("restore_status", ""),
        "steps": steps,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "step_count": len(steps),
            "ready_step_count": sum(1 for step in steps if step["status"] == "ready"),
            "blocked_step_count": sum(1 for step in steps if step["status"] == "blocked"),
            "finding_count": len(findings),
            "ready_for_restore": not findings and all(step["status"] == "ready" for step in steps),
        },
        "sourceRefs": sorted(set(source_refs + list(report.get("sourceRefs", [])))),
    }
    return apply_productization_contract_tree(runbook, source_refs=source_refs)


def write_store_dr_runbook(runbook: dict[str, Any], out_path: str | Path) -> dict[str, Any]:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    apply_productization_contract_tree(runbook, source_refs=list(runbook.get("sourceRefs", [])))
    path.write_text(json.dumps(runbook, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return {
        "schema_version": "HATE/v1",
        "record_type": "store-dr-runbook-artifact",
        **productization_envelope(runbook, report_id=f"{runbook.get('runbook_id') or 'store-dr-runbook'}:artifact", source_refs=list(runbook.get("sourceRefs", []))),
        "readiness_effect": str(runbook.get("readiness_effect") or "none"),
        "artifact_path": str(path),
        "step_count": len(runbook.get("steps", [])),
        "sourceRefs": list(runbook.get("sourceRefs", [])),
    }


def _runbook_steps_for(
    backup: dict[str, Any],
    restore: dict[str, Any],
    drill: dict[str, Any],
    summary: dict[str, Any],
    source_ref: str,
) -> list[dict[str, Any]]:
    return [
        _runbook_step("verify_backup_inventory", bool(backup.get("backup_id") and backup.get("backup_manifest_ref") and backup.get("created_at")), "Verify backup id, manifest, and creation timestamp.", source_ref),
        _runbook_step("verify_backup_hash", bool(backup.get("source_store_hash") and backup.get("backup_hash") and backup.get("source_store_hash") == backup.get("backup_hash")), "Verify backup hash matches source store hash.", source_ref),
        _runbook_step("verify_corruption_scan", drill.get("corruption_scan_result") == "pass", "Run or verify corruption scan before restore.", source_ref),
        _runbook_step("restore_store", restore.get("restore_status") == "restored", "Restore store from selected backup.", source_ref),
        _runbook_step("verify_legal_hold", bool(summary.get("legal_hold_preserved")), "Verify legal hold count is preserved or increased.", source_ref),
        _runbook_step("verify_rpo", summary.get("rpo_budget_status") != "exceeded", "Verify RPO budget is within limit.", source_ref),
        _runbook_step("verify_rto", summary.get("rto_budget_status") != "exceeded", "Verify RTO budget is within limit.", source_ref),
        _runbook_step("rebuild_projection", restore.get("projection_rebuild_status") == "complete", "Rebuild read models/projections after restore.", source_ref),
    ]


def _runbook_step(step_id: str, ready: bool, description: str, source_ref: str) -> dict[str, Any]:
    return {
        "record_type": "store-dr-runbook-step",
        **productization_envelope({"system_actor": "hate-local"}, report_id=f"store-dr-runbook-step:{step_id}", source_refs=[source_ref]),
        "readiness_effect": "none" if ready else "hold",
        "step_id": step_id,
        "status": "ready" if ready else "blocked",
        "description": description,
        "required": True,
        "sourceRefs": [source_ref],
    }


def _runbook_findings(
    report: dict[str, Any],
    steps: list[dict[str, Any]],
    source_ref: str,
) -> list[StoreDrFinding]:
    findings = [
        _finding("dr_runbook_step_blocked", f"DR runbook step blocked: {step['step_id']}.", source_ref)
        for step in steps
        if step["status"] == "blocked"
    ]
    if report.get("findings"):
        findings.append(_finding("dr_runbook_blocked_by_report_findings", "DR runbook cannot be ready while DR report has findings.", source_ref))
    return findings


def _normalize_operation(raw: dict[str, Any]) -> dict[str, Any]:
    operation = dict(raw or {})
    return {
        "backup_id": str(operation.get("backup_id") or ""),
        "backup_manifest_ref": str(operation.get("backup_manifest_ref") or ""),
        "created_at": str(operation.get("created_at") or ""),
        "source_store_hash": str(operation.get("source_store_hash") or ""),
        "backup_hash": str(operation.get("backup_hash") or ""),
        "restore_hash": str(operation.get("restore_hash") or ""),
        "legal_hold_count_before": _int(operation.get("legal_hold_count_before"), 0),
        "legal_hold_count_after": _int(operation.get("legal_hold_count_after"), 0),
        "rpo_seconds": _int(operation.get("rpo_seconds"), 0),
        "rpo_budget_seconds": _int(operation.get("rpo_budget_seconds"), -1),
        "rto_seconds": _int(operation.get("rto_seconds"), 0),
        "rto_budget_seconds": _int(operation.get("rto_budget_seconds"), -1),
        "corruption_scan_result": str(operation.get("corruption_scan_result") or "not_run"),
        "projection_rebuild_status": str(operation.get("projection_rebuild_status") or "not_run"),
        "restore_status": str(operation.get("restore_status") or "restored"),
    }


def _backup_operation(operation: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_type": "store-backup-operation",
        "backup_id": operation["backup_id"],
        "backup_manifest_ref": operation["backup_manifest_ref"],
        "created_at": operation["created_at"],
        "source_store_hash": operation["source_store_hash"],
        "backup_hash": operation["backup_hash"],
        "legal_hold_count_before": operation["legal_hold_count_before"],
        "corruption_scan_result": operation["corruption_scan_result"],
    }


def _restore_operation(operation: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_type": "store-restore-operation",
        "backup_id": operation["backup_id"],
        "restore_hash": operation["restore_hash"],
        "restore_status": operation["restore_status"],
        "legal_hold_count_after": operation["legal_hold_count_after"],
        "rpo_seconds": operation["rpo_seconds"],
        "rto_seconds": operation["rto_seconds"],
        "projection_rebuild_status": operation["projection_rebuild_status"],
    }


def _drill_result(operation: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_type": "store-dr-drill-result",
        "backup_id": operation["backup_id"],
        "source_store_hash": operation["source_store_hash"],
        "backup_hash": operation["backup_hash"],
        "restore_hash": operation["restore_hash"],
        "legal_hold_count_before": operation["legal_hold_count_before"],
        "legal_hold_count_after": operation["legal_hold_count_after"],
        "rpo_seconds": operation["rpo_seconds"],
        "rto_seconds": operation["rto_seconds"],
        "corruption_scan_result": operation["corruption_scan_result"],
        "projection_rebuild_status": operation["projection_rebuild_status"],
    }


def _findings_for(operation: dict[str, Any], source_ref: str) -> list[StoreDrFinding]:
    findings: list[StoreDrFinding] = []
    if not operation["backup_id"] or not operation["backup_manifest_ref"] or not operation["created_at"]:
        findings.append(_finding("dr_backup_inventory_missing", "Backup inventory or manifest reference is missing.", source_ref))
    if operation["backup_hash"] and operation["source_store_hash"] and operation["backup_hash"] != operation["source_store_hash"]:
        findings.append(_finding("dr_backup_hash_mismatch", "Backup hash does not match source store hash.", source_ref))
    if operation["corruption_scan_result"] != "pass":
        findings.append(_finding("dr_corrupt_backup_denied", "Corrupt or unscanned backup cannot become canonical evidence.", source_ref))
    if operation["legal_hold_count_after"] < operation["legal_hold_count_before"]:
        findings.append(_finding("dr_legal_hold_lost", "Legal hold count decreased after restore.", source_ref))
    if operation["rto_budget_seconds"] >= 0 and operation["rto_seconds"] > operation["rto_budget_seconds"]:
        findings.append(_finding("dr_restore_rto_exceeded", "Restore drill exceeded RTO budget.", source_ref))
    if operation["projection_rebuild_status"] != "complete":
        findings.append(_finding("dr_projection_rebuild_failed", "Projection rebuild did not complete after restore.", source_ref))
    return findings


def _finding(code: str, message: str, source_ref: str) -> StoreDrFinding:
    return StoreDrFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
        readiness_effect="hold",
    )


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
