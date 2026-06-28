from __future__ import annotations

from typing import Any

SCHEMA_VERSION = "HATE/v1"


def build_retention_governance_report(
    run_id: str,
    artifact_budget: dict[str, Any],
    domain_model: dict[str, Any],
) -> dict[str, Any]:
    policies = _classification_policies(domain_model)
    artifact_actions = [
        _artifact_action(item, policies)
        for item in artifact_budget.get("artifacts", [])
        if isinstance(item, dict)
    ]
    request_fixtures = [
        {
            "request_id": "req_export_internal_summary",
            "request_type": "customer_export",
            "classification": "internal",
            "decision": "allow_metadata_only",
            "raw_artifact_included": False,
            "source_refs": ["artifact-budget-report.json"],
        },
        {
            "request_id": "req_delete_restricted_quarantine",
            "request_type": "customer_delete",
            "classification": "restricted",
            "decision": "defer_to_system_of_record",
            "raw_artifact_deleted_by_hate": False,
            "quarantine_metadata_retained": True,
            "source_refs": ["privacy-quarantine-report.json"],
        },
        {
            "request_id": "req_legal_hold_trace",
            "request_type": "legal_hold",
            "classification": "confidential",
            "decision": "hold_metadata_and_block_delete",
            "delete_allowed_while_on_hold": False,
            "source_refs": ["domain-model-report.json"],
        },
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "retention_governance_report",
        "run_id": run_id,
        "policy_scope": "metadata_policy_not_system_of_record",
        "classification_policies": policies,
        "artifact_actions": artifact_actions,
        "request_fixtures": request_fixtures,
        "legal_hold": {
            "supported": True,
            "delete_allowed_while_on_hold": False,
            "canonical_bundle_mutated": False,
            "qeg_retention_reimplemented": False,
        },
        "customer_export_delete": {
            "export_metadata_only": True,
            "delete_request_records_metadata": True,
            "raw_artifact_deletion_delegated": True,
            "system_of_record": "QEG or connected storage policy",
        },
        "summary": {
            "classification_count": len(policies),
            "artifact_action_count": len(artifact_actions),
            "request_fixture_count": len(request_fixtures),
            "restricted_quarantine_count": sum(1 for item in artifact_actions if item["classification"] == "restricted"),
            "legal_hold_blocks_delete": True,
        },
        "source_refs": [
            "docs/process/ENTERPRISE_DOMAIN_MODEL.md",
            "docs/process/PRIVACY_QUARANTINE_CONTRACT.md",
            "artifact-budget-report.json",
            "domain-model-report.json",
        ],
        "precheck_decision_override": False,
        "qeg_verdict_override": False,
        "release_gate_override": False,
        "publish_gate_override": False,
    }


def _classification_policies(domain_model: dict[str, Any]) -> list[dict[str, Any]]:
    policies = []
    for item in domain_model.get("classification_policy", []):
        classification = str(item.get("classification", "internal"))
        policies.append({
            "classification": classification,
            "retention_days": item.get("default_retention_days", 90),
            "summary_allowed": item.get("summary_allowed", False),
            "export_allowed": item.get("export_allowed", False),
            "diagnostic_allowed": item.get("diagnostic_allowed", False),
            "delete_action": "quarantine_metadata_only" if classification == "restricted" else "metadata_delete_request",
            "legal_hold_action": "block_delete_retain_metadata",
            "final_retention_control": "delegated_to_qeg_or_connected_storage",
        })
    return policies


def _artifact_action(artifact: dict[str, Any], policies: list[dict[str, Any]]) -> dict[str, Any]:
    classification = str(artifact.get("classification") or _classification_for_kind(str(artifact.get("kind", ""))))
    policy = next((item for item in policies if item["classification"] == classification), None)
    retention_days = artifact.get("retention_days") or (policy or {}).get("retention_days", 90)
    legal_hold = bool(artifact.get("legal_hold", False))
    return {
        "artifact_ref": artifact.get("artifact_ref", ""),
        "artifact_kind": artifact.get("kind", ""),
        "classification": classification,
        "retention_days": retention_days,
        "legal_hold": legal_hold,
        "delete_allowed": not legal_hold and classification not in {"restricted"},
        "export_allowed": bool((policy or {}).get("export_allowed", False)) if classification != "internal" else "metadata_only",
        "diagnostic_allowed": bool((policy or {}).get("diagnostic_allowed", False)),
        "raw_artifact_included_in_export": False,
        "canonical_bundle_mutated": False,
    }


def _classification_for_kind(kind: str) -> str:
    if kind in {"trace", "screenshot", "video"}:
        return "confidential"
    if kind in {"secret", "pii", "unsafe"}:
        return "restricted"
    if kind in {"coverage", "sarif", "test-results"}:
        return "internal"
    return "public"
