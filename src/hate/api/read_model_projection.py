"""Canonical report projection for the HATE API read model."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .read_model_contract import STALENESS_FRESH, STALENESS_STALE


def build_read_model(
    reports: dict[str, Any],
    required_reports: list[str] | None = None,
    staleness_status: str = STALENESS_FRESH,
    staleness_reason: str | None = None,
) -> dict[str, Any]:
    """Project canonical HATE reports into API read-model resources.

    The projection copies verdict/status fields from upstream reports. It does
    not recompute readiness or turn missing reports into success.
    """
    required_reports = required_reports or []
    missing_reports = [name for name in required_reports if name not in reports]
    source_refs: list[str] = []
    for report in reports.values():
        if isinstance(report, dict):
            source_refs.extend(report.get("sourceRefs", []))

    run_report = reports.get("run", {})
    readiness_report = reports.get("readiness", {})
    readiness_summary = readiness_report.get("summary", {})
    risk_matrix = reports.get("risk_coverage_matrix", {})
    artifact_safety = reports.get("artifact_safety", {})
    manual_review_report = reports.get("manual_review", {})
    evidence_graph = reports.get("evidence_graph", {})
    operating_projection = reports.get("operating_projection", {})
    connector_sync = reports.get("connector_sync", {})

    run_id = (
        run_report.get("run_id")
        or readiness_report.get("run_id")
        or risk_matrix.get("run_id")
        or artifact_safety.get("run_id")
    )
    decision = (
        run_report.get("decision")
        or readiness_summary.get("overall_status")
        or readiness_report.get("overall_status")
        or "unknown"
    )

    runs: list[dict[str, Any]] = []
    if run_id:
        runs.append({
            "run_id": run_id,
            "attempt": run_report.get("attempt", 1),
            "commit": run_report.get("commit", run_report.get("source_version", "")),
            "profile": run_report.get("profile", readiness_report.get("profile", "default")),
            "decision": decision,
            "dq_count": readiness_summary.get("hard_dq_count", len(readiness_report.get("hard_dqs", []))),
            "gap_count": readiness_summary.get("soft_gap_count", len(readiness_report.get("soft_gaps", []))),
            "created_at": run_report.get("created_at") or readiness_report.get("generated_at"),
            "source_refs": run_report.get("sourceRefs", []) + readiness_report.get("sourceRefs", []),
        })

    risks = []
    for risk in risk_matrix.get("risks", []):
        risks.append({
            "risk_id": risk.get("risk_id"),
            "severity": risk.get("severity"),
            "owner": risk.get("owner"),
            "layer": risk.get("layer"),
            "changed_entity": risk.get("changed_entity") or risk.get("description"),
            "required_evidence": risk.get("required_evidence_classes") or risk.get("required_evidence", []),
            "current_evidence": risk.get("observed_evidence_classes") or risk.get("current_evidence", []),
            "oracle_status": "missing" if risk.get("oracle_evidence") is False else "present",
            "manual_required": bool(risk.get("manual_required")),
            "debt_status": risk.get("debt_status"),
            "gap": risk.get("gap_class") not in (None, "pass"),
            "source_refs": risk.get("sourceRefs", []) or ([risk["sourceRef"]] if risk.get("sourceRef") else []),
        })

    artifacts = []
    for artifact in artifact_safety.get("artifacts", []):
        artifacts.append(_safe_artifact_metadata(artifact))
    if artifact_safety.get("artifact_id"):
        artifacts.append(_safe_artifact_metadata(artifact_safety))

    findings = []
    for report_key in ("artifact_safety", "manual_review", "readiness"):
        report = reports.get(report_key, {})
        for finding in report.get("findings", []) + report.get("hard_dqs", []):
            findings.append({
                "finding_id": finding.get("finding_id") or finding.get("code") or finding.get("id"),
                "severity": finding.get("severity", finding.get("readiness_effect", "info")),
                "category": finding.get("category", report_key),
                "message": finding.get("message") or finding.get("reason", ""),
                "remediation": finding.get("remediation") or finding.get("suggested_manual_review_action"),
                "source_refs": finding.get("sourceRefs", []) or ([finding["sourceRef"]] if finding.get("sourceRef") else []),
            })
    for finding in operating_projection.get("findings", []) + connector_sync.get("findings", []):
        findings.append({
            "finding_id": finding.get("code") or finding.get("finding_id") or finding.get("id"),
            "severity": finding.get("severity", finding.get("readiness_effect", "info")),
            "category": "operating" if "operating_record_id" in finding else "connector_sync",
            "message": finding.get("message", ""),
            "remediation": finding.get("remediation"),
            "source_refs": finding.get("sourceRefs", []),
            "operating_record_id": finding.get("operating_record_id", ""),
        })

    manual_review_requests = manual_review_report.get("requests", [])
    if manual_review_report.get("record_type") == "manual_review_request_bundle":
        manual_review_requests = manual_review_report.get("manual_review_requests", manual_review_requests)

    evidence = []
    for node in evidence_graph.get("nodes", []):
        if node.get("kind") in {"test_result", "coverage_slice", "static_finding", "contract_evidence", "mutation_evidence"}:
            evidence.append({
                "evidence_id": node.get("id"),
                "kind": node.get("kind"),
                "status": node.get("status", node.get("result")),
                "trust_score": node.get("trust_score"),
                "source_refs": node.get("sourceRefs", []) or ([node["sourceRef"]] if node.get("sourceRef") else []),
                "artifact_refs": node.get("artifact_refs", []),
            })

    operating_records = [_project_operating_record(record) for record in operating_projection.get("records", [])]
    connector_sync_payloads = [
        _project_connector_payload(payload, status="accepted")
        for payload in connector_sync.get("accepted_payloads", [])
    ]
    connector_sync_payloads.extend(
        _project_connector_payload(payload, status="denied")
        for payload in connector_sync.get("denied_payloads", [])
    )
    connector_sync_payloads.extend(
        _project_connector_payload(payload, status="skipped_duplicate")
        for payload in connector_sync.get("skipped_duplicate_payloads", [])
    )

    diagnostics = []
    for report_name in missing_reports:
        diagnostics.append({
            "code": "missing_upstream_report",
            "finding_id": "missing_upstream_report",
            "category": "read_model",
            "severity": "hold",
            "message": f"Required upstream report is missing: {report_name}",
            "sourceRef": f"api/read_model:{report_name}",
        })

    if missing_reports and staleness_status == STALENESS_FRESH:
        staleness_status = STALENESS_STALE
        staleness_reason = "missing required upstream report"

    bundle_hash = reports.get("bundle_hash") or run_report.get("bundle_hash") or readiness_report.get("bundle_hash")

    return {
        "runs": runs,
        "run_details": {run["run_id"]: {
            "run_id": run["run_id"],
            "attempt": run["attempt"],
            "provenance": run_report.get("provenance", {
                "repo": run_report.get("repo"),
                "branch": run_report.get("branch"),
                "commit": run["commit"],
                "actor": run_report.get("actor"),
                "triggered_at": run.get("created_at"),
            }),
            "inputs": run_report.get("inputs", {"profile": run["profile"]}),
            "outputs": readiness_summary or {"decision": run["decision"]},
            "source_refs": run["source_refs"],
        } for run in runs},
        "evidence": evidence,
        "risks": risks,
        "artifacts": artifacts,
        "findings": findings + diagnostics,
        "manual_review_requests": manual_review_requests,
        "operating_records": operating_records,
        "connector_sync_payloads": connector_sync_payloads,
        "readiness_summaries": [readiness_summary] if readiness_summary else [],
        "sourceRefs": source_refs,
        "source": {
            "bundle_hash": bundle_hash,
            "run_id": run_id,
            "attempt": runs[0]["attempt"] if runs else None,
        },
        "staleness": {
            "status": staleness_status,
            "reason": staleness_reason,
            "last_rebuild_at": reports.get("last_rebuild_at"),
        },
        "diagnostics": diagnostics,
    }


def default_read_model() -> dict[str, Any]:
    """Minimal empty read model used when callers do not pass report data."""
    return build_read_model(
        {
            "run": {
                "run_id": "run-001",
                "attempt": 1,
                "commit": "abc123",
                "profile": "default",
                "decision": "PASS",
                "created_at": datetime.now(UTC).isoformat(),
                "sourceRefs": ["api/read_model:default-run"],
            },
            "readiness": {
                "summary": {"overall_status": "PASS", "hard_dq_count": 0, "soft_gap_count": 0},
                "sourceRefs": ["api/read_model:default-readiness"],
            },
        }
    )


def _safe_artifact_metadata(artifact: dict[str, Any]) -> dict[str, Any]:
    """Return artifact metadata safe for API/UI surfaces."""
    classification = artifact.get("classification", "restricted")
    quarantine_status = artifact.get("quarantine_status")
    if not quarantine_status:
        quarantine_status = "quarantined" if classification in {"restricted", "secret", "pii"} else "none"
    redaction_status = artifact.get("redaction_status", "not_required")
    safe_metadata = artifact.get("safe_metadata", {})
    if not safe_metadata:
        safe_metadata = {
            "artifact_id": artifact.get("artifact_id"),
            "classification": classification,
            "safe_for_summary": quarantine_status == "none",
        }
    return {
        "artifact_id": artifact.get("artifact_id"),
        "classification": classification,
        "quarantine_status": quarantine_status,
        "redaction_status": redaction_status,
        "safe_metadata": safe_metadata,
        "source_refs": artifact.get("sourceRefs", []) or ([artifact["sourceRef"]] if artifact.get("sourceRef") else []),
    }


def _project_operating_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "operating_record_id": record.get("operating_record_id", ""),
        "entity_kind": record.get("entity_kind", ""),
        "entity_id": record.get("entity_id", ""),
        "status": record.get("status", ""),
        "severity": record.get("severity", ""),
        "readiness_effect": record.get("readiness_effect", ""),
        "owner": record.get("owner", ""),
        "due_date": record.get("due_date", ""),
        "expiry_date": record.get("expiry_date", ""),
        "source_refs": record.get("sourceRefs", []),
        "evidence_refs": record.get("evidence_refs", []),
        "decision_basis": record.get("decision_basis", []),
        "tracker_sync_count": len(record.get("tracker_syncs", [])),
        "notification_count": len(record.get("notifications", [])),
    }


def _project_connector_payload(payload: dict[str, Any], *, status: str) -> dict[str, Any]:
    return {
        "sync_id": payload.get("sync_id", ""),
        "operating_record_id": payload.get("operating_record_id", ""),
        "connector_id": payload.get("connector_id", ""),
        "external_system": payload.get("external_system", ""),
        "direction": payload.get("direction", ""),
        "operation": payload.get("operation", ""),
        "state": payload.get("state", ""),
        "status": status,
        "payload_hash": payload.get("payload_hash", ""),
        "safe_summary": payload.get("safe_summary", {}),
        "source_refs": payload.get("sourceRefs", []),
    }
