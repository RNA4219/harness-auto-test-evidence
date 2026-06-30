"""Workflow-cookbook cross-repo plugin integration evaluation for HATE-GAP-025."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


REQUIRED_SURFACES = {
    "task_sync": "workflow_plugin_task_sync_missing",
    "acceptance_sync": "workflow_plugin_acceptance_sync_missing",
    "docs_stale_check": "workflow_plugin_docs_stale_check_missing",
    "schema_valid": "workflow_plugin_schema_invalid",
}


@dataclass(frozen=True)
class WorkflowPluginFinding:
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


def evaluate_workflow_plugin_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_workflow_plugin_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "workflow-plugin-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_workflow_plugin_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "workflow-plugin-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["workflow-plugin"])
    plugin_config = _normalize_plugin_config(input_data.get("plugin_config", input_data))
    sync_result = _normalize_sync_result(input_data.get("sync_result", {}))
    findings = _findings_for(plugin_config, sync_result, source_refs[0])
    status = "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": "workflow-plugin-report",
        "report_id": report_id,
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "plugin_config": plugin_config,
        "sync_result": sync_result,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "repository_count": len(plugin_config["repositories"]),
            "required_surface_count": len(REQUIRED_SURFACES) + 1,
            "missing_repository_count": len(plugin_config["missing_repositories"]),
            "done_tasks_without_acceptance_count": len(sync_result["done_tasks_without_acceptance"]),
            "finding_count": len(findings),
        },
        "sourceRefs": sorted(set(source_refs)),
    }


def _normalize_plugin_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw_config or {})
    repositories = [str(repo) for repo in config.get("repositories", []) if str(repo)]
    return {
        "repositories": repositories,
        "task_sync": bool(config.get("task_sync", False)),
        "acceptance_sync": bool(config.get("acceptance_sync", False)),
        "docs_stale_check": bool(config.get("docs_stale_check", False)),
        "evidence_bridge": bool(config.get("evidence_bridge", True)),
        "schema_valid": bool(config.get("schema_valid", False)),
        "missing_repositories": list(config.get("missing_repositories") or []),
        "missing_tasks": list(config.get("missing_tasks") or []),
        "missing_acceptance": list(config.get("missing_acceptance") or []),
        "missing_schemas": list(config.get("missing_schemas") or []),
        "product_ready_claim": bool(config.get("product_ready_claim", False)),
    }


def _normalize_sync_result(raw_result: dict[str, Any]) -> dict[str, Any]:
    result = dict(raw_result or {})
    return {
        "done_tasks_without_acceptance": list(result.get("done_tasks_without_acceptance") or []),
        "docs_stale": bool(result.get("docs_stale", False)),
        "evidence_bridge_records_missing": bool(result.get("evidence_bridge_records_missing", False)),
    }


def _findings_for(
    plugin_config: dict[str, Any],
    sync_result: dict[str, Any],
    source_ref: str,
) -> list[WorkflowPluginFinding]:
    findings: list[WorkflowPluginFinding] = []
    if len(plugin_config["repositories"]) < 2:
        findings.append(_finding(
            "workflow_plugin_cross_repo_config_missing",
            "Cross-repo plugin config must name HATE and workflow-cookbook repositories.",
            source_ref,
        ))
    for surface, code in REQUIRED_SURFACES.items():
        if not plugin_config[surface]:
            findings.append(_finding(code, f"Required workflow plugin surface is missing: {surface}.", source_ref))
    if not plugin_config["evidence_bridge"]:
        findings.append(_finding(
            "workflow_plugin_evidence_bridge_missing",
            "Workflow plugin integration must expose agent-protocols Evidence JSONL.",
            source_ref,
        ))
    if _has_missing_reference(plugin_config):
        findings.append(_finding(
            "workflow_plugin_missing_reference",
            "Plugin config references a missing repository, task, acceptance record, or schema.",
            source_ref,
        ))
    if sync_result["done_tasks_without_acceptance"]:
        findings.append(_finding(
            "workflow_task_acceptance_drift",
            "Task marked done while acceptance sync reports missing acceptance.",
            source_ref,
        ))
    if plugin_config["product_ready_claim"] and sync_result["docs_stale"]:
        findings.append(_finding(
            "workflow_plugin_docs_stale_ignored",
            "Product-ready claim must not ignore stale docs report.",
            source_ref,
        ))
    if sync_result["evidence_bridge_records_missing"]:
        findings.append(_finding(
            "workflow_plugin_evidence_bridge_records_missing",
            "Evidence bridge surface is configured but required evidence records are missing.",
            source_ref,
        ))
    return findings


def _has_missing_reference(plugin_config: dict[str, Any]) -> bool:
    return any(
        plugin_config[key]
        for key in ("missing_repositories", "missing_tasks", "missing_acceptance", "missing_schemas")
    )


def _finding(code: str, message: str, source_ref: str) -> WorkflowPluginFinding:
    return WorkflowPluginFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
    )
