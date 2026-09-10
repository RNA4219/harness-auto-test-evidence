"""P1A doctor report generation with findings taxonomy."""

from __future__ import annotations

from typing import Any

from hate.p1a_export_metadata import export_metadata_issues
from hate.p1a_graph import analyze_graph, valid_source_refs
from hate.p1a_internal.retry_aggregation import _build_retry_aggregation
from hate.p1a_precheck import precheck_gaps, precheck_permission_issues
from hate.p1a_provenance import analyze_provenance
from hate.p1a_schema import bundle_schema_issues

SCHEMA_VERSION = "HATE/v1"


def _build_doctor_report(
    run_id: str,
    run_attempt: int,
    bundle: dict[str, Any],
    report: dict[str, Any],
    resolver_map: dict[str, Any],
    retry_aggregation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    for issue in bundle_schema_issues(bundle):
        findings.append(_doctor_finding({
            "finding_id": f"doctor:schema:{len(findings) + 1}",
            "category": "schema", **issue,
        }))
    for issue in analyze_graph(bundle, run_id).issues:
        findings.append(_doctor_finding({
            "finding_id": f"doctor:qeg_fixture:{len(findings) + 1}",
            "category": "qeg_fixture", "severity": "high",
            **issue, "source_refs": ["qeg-bundle.json"],
        }))
    for issue in analyze_provenance(bundle, report).issues:
        findings.append(_doctor_finding({
            "finding_id": f"doctor:provenance:{len(findings) + 1}",
            "category": "provenance", "severity": "high", **issue,
        }))
    for issue in export_metadata_issues(bundle, report):
        findings.append(_doctor_finding({
            "finding_id": f"doctor:export:{len(findings) + 1}", "category": "export", **issue,
        }))
    if retry_aggregation is None:
        retry_aggregation = _build_retry_aggregation(run_id, run_attempt, bundle)
    for issue in retry_aggregation["issues"]:
        findings.append(_doctor_finding({
            "finding_id": f"doctor:retry:{len(findings) + 1}",
            "category": "retry", "severity": "medium", **issue, "source_refs": ["qeg-bundle.json"],
        }))
    for issue in precheck_permission_issues(bundle):
        findings.append(_doctor_finding({
            "finding_id": f"doctor:precheck:{len(findings) + 1}",
            "category": "precheck", "severity": "high", **issue,
        }))
    for gap in precheck_gaps(bundle):
        findings.append(_doctor_finding({
            "finding_id": f"doctor:precheck:{len(findings) + 1}",
            "category": "precheck", "severity": "medium", **gap,
        }))
    for claim in report.get("unsupportedClaims", []):
        findings.append(_doctor_finding({
            "finding_id": f"doctor:qeg_fixture:{len(findings) + 1}",
            "category": "qeg_fixture",
            "severity": "high",
            "message": claim.get("reason", "unsupported claim"),
            "source_refs": ["qeg-export-report.json"],
        }))
    for artifact in report.get("excludedArtifacts", []):
        findings.append(_doctor_finding({
            "finding_id": f"doctor:artifact_safety:{len(findings) + 1}",
            "category": "artifact_safety",
            "severity": "critical",
            "message": artifact.get("reason", "artifact excluded"),
            "source_refs": ["qeg-export-report.json"],
        }))
    if not _all_source_refs_non_empty(bundle.get("nodes", []), bundle.get("edges", [])):
        findings.append(_doctor_finding({
            "finding_id": f"doctor:qeg_fixture:{len(findings) + 1}",
            "category": "qeg_fixture",
            "severity": "high",
            "message": "node or edge has missing or blank sourceRefs" if bundle.get("nodes") or bundle.get("edges")
                       else "graph has no nodes or edges",
            "source_refs": ["qeg-bundle.json"],
        }))
    for entry in resolver_map.get("entries", []):
        if entry.get("resolution_status") == "unsafe":
            findings.append(_doctor_finding({
                "finding_id": f"doctor:path:{len(findings) + 1}",
                "category": "path",
                "severity": "high",
                "message": "unsafe source reference path",
                "source_refs": [entry.get("original", "")],
            }))
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "doctor_report",
        "run_id": run_id,
        "run_attempt": run_attempt,
        "findings": findings,
        "summary": {
            "finding_count": len(findings),
            "blocking_categories": sorted({f["category"] for f in findings if f["severity"] in {"high", "critical"}}),
            "by_category": _count_by(findings, "category"),
            "by_severity": _count_by(findings, "severity"),
            "taxonomy_version": "doctor-taxonomy-2026-06-29",
        },
        "release_gate_override": False,
        "publish_gate_override": False,
    }


def _doctor_finding(finding: dict[str, Any]) -> dict[str, Any]:
    category = str(finding.get("category", "unknown"))
    severity = str(finding.get("severity", "medium"))
    taxonomy = {
        "qeg_fixture": ("HATE-DOC-QEG-001", "Review QEG bundle/report sourceRefs and unsupported claims."),
        "artifact_safety": ("HATE-DOC-ART-001", "Redact, quarantine, or replace unsafe artifact evidence."),
        "path": ("HATE-DOC-PATH-001", "Normalize or remove unsafe path references before export."),
        "schema": ("HATE-DOC-SCH-001", "Validate generated artifacts against the schema registry."),
        "profile": ("HATE-DOC-PROF-001", "Check profile support and inheritance drift."),
        "adapter": ("HATE-DOC-ADP-001", "Check adapter manifest and conformance fixture coverage."),
        "provenance": ("HATE-DOC-PROV-001", "Restore valid run, commit, timestamp, and declared artifact SHA256 evidence."),
        "retry": ("HATE-DOC-RETRY-001", "Review retry order, matrix grouping, and shard completeness using the original execution records."),
        "precheck": ("HATE-DOC-PRE-001", "Review the original precheck reasons and permission conditions before regenerating the bundle from corrected evidence."),
        "export": ("HATE-DOC-EXP-001", "Review the original export status and schema validation report, then regenerate formal evidence from corrected source artifacts."),
    }
    code, remediation = taxonomy.get(category, ("HATE-DOC-UNK-001", "Inspect the finding and attach source-backed remediation."))
    return {
        "finding_code": code,
        "taxonomy_version": "doctor-taxonomy-2026-06-29",
        "blocking": severity in {"high", "critical"},
        "remediation": remediation,
        **finding,
    }


def _count_by(items: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(field, "unknown"))
        counts[value] = counts.get(value, 0) + 1
    return counts


def _all_source_refs_non_empty(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> bool:
    if not nodes and not edges:
        return False
    for node in nodes:
        if not valid_source_refs(node.get("sourceRefs")):
            return False
    for edge in edges:
        if not valid_source_refs(edge.get("traceability", {}).get("sourceRefs")):
            return False
    return True
