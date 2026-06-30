"""Workflow-cookbook Evidence protocol evaluation for HATE-GAP-023."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


EVIDENCE_CLASSES = {
    "command_execution",
    "artifact_generation",
    "decision_record",
    "review_record",
    "runtime_event",
}
REQUIRED_FIELDS = {
    "evidence_id",
    "source_tool",
    "command_or_action",
    "artifact_refs",
    "hashes",
    "decision_or_status",
    "timestamp",
    "sourceRefs",
}


@dataclass(frozen=True)
class EvidenceFinding:
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


def evaluate_evidence_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_evidence_protocol_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "workflow-evidence-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_evidence_protocol_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "workflow-evidence-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["workflow-evidence"])
    evidence = _normalize_evidence(input_data.get("evidence", input_data))
    findings = _findings_for(evidence, source_refs[0])
    status = "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": "workflow-evidence-report",
        "report_id": report_id,
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "evidence": evidence,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "evidence_id": evidence.get("evidence_id", ""),
            "evidence_class": evidence.get("evidence_class", ""),
            "artifact_ref_count": len(evidence.get("artifact_refs", [])),
            "finding_count": len(findings),
        },
        "sourceRefs": sorted(set(source_refs)),
    }


def _normalize_evidence(raw_evidence: dict[str, Any]) -> dict[str, Any]:
    evidence = dict(raw_evidence or {})
    evidence["artifact_refs"] = list(evidence.get("artifact_refs") or [])
    evidence["hashes"] = dict(evidence.get("hashes") or {})
    evidence["sourceRefs"] = list(evidence.get("sourceRefs") or [])
    return evidence


def _findings_for(evidence: dict[str, Any], source_ref: str) -> list[EvidenceFinding]:
    findings: list[EvidenceFinding] = []
    missing_fields = sorted(field for field in REQUIRED_FIELDS if not _field_present(evidence, field))
    if missing_fields:
        findings.append(_finding(
            "evidence_missing_required_field",
            f"Evidence record missing required fields: {', '.join(missing_fields)}",
            source_ref,
        ))
    evidence_class = evidence.get("evidence_class")
    if evidence_class not in EVIDENCE_CLASSES:
        findings.append(_finding(
            "evidence_class_unknown",
            f"Evidence class is not supported: {evidence_class}",
            source_ref,
        ))
    missing_hash_refs = [
        ref for ref in evidence.get("artifact_refs", [])
        if not evidence.get("hashes", {}).get(ref)
    ]
    if missing_hash_refs:
        findings.append(_finding(
            "evidence_artifact_missing_hash",
            f"Evidence artifact refs missing hashes: {', '.join(missing_hash_refs)}",
            source_ref,
        ))
    if evidence_class == "command_execution" and "exit_status" not in evidence:
        findings.append(_finding(
            "evidence_command_missing_exit_status",
            "Command execution evidence requires exit_status.",
            source_ref,
        ))
    if evidence_class == "review_record" and not evidence.get("scope"):
        findings.append(_finding(
            "evidence_review_missing_scope",
            "Review evidence requires scope.",
            source_ref,
        ))
    return findings


def _field_present(evidence: dict[str, Any], field: str) -> bool:
    if field == "hashes":
        return field in evidence and isinstance(evidence.get(field), dict)
    value = evidence.get(field)
    if isinstance(value, (list, dict)):
        return bool(value)
    return value is not None and value != ""


def _finding(code: str, message: str, source_ref: str) -> EvidenceFinding:
    return EvidenceFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
    )
