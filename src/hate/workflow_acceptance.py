"""Workflow-cookbook acceptance linkage evaluation for HATE-GAP-022."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


REQUIRED_HEADINGS = {"Scope", "Requirements", "Verification", "Evidence", "Open Risks", "Decision"}
AC_PATH_PATTERN = re.compile(r"^docs/acceptance/(AC-\d{8}-\d{2}|HATE_GAP_CLOSURE_ACCEPTANCE)\.md$")
ACCEPTANCE_STATES = {"accepted", "conditionally_accepted", "held"}


@dataclass(frozen=True)
class AcceptanceFinding:
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


def evaluate_acceptance_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_acceptance_linkage_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "workflow-acceptance-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_acceptance_linkage_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "workflow-acceptance-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["workflow-acceptance"])
    linkage = _normalize_linkage(input_data)
    findings = _findings_for(linkage, source_refs[0])
    status = "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": "workflow-acceptance-report",
        "report_id": report_id,
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "acceptance_linkage": linkage,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "task_status": linkage["task_status"],
            "acceptance_path": linkage["acceptance_record"]["path"],
            "evidence_ref_count": len(linkage["acceptance_record"]["evidence_refs"]),
            "finding_count": len(findings),
        },
        "sourceRefs": sorted(set(source_refs)),
    }


def _normalize_linkage(input_data: dict[str, Any]) -> dict[str, Any]:
    record = input_data.get("acceptance_record") or {}
    if not isinstance(record, dict):
        record = {}
    headings = record.get("headings")
    if headings is None and record:
        headings = sorted(REQUIRED_HEADINGS)
    return {
        "task_status": str(input_data.get("task_status") or "planned"),
        "exception_reason": str(input_data.get("exception_reason") or ""),
        "acceptance_record": {
            "path": str(record.get("path") or ""),
            "state": str(record.get("state") or ""),
            "headings": list(headings or []),
            "evidence_refs": list(record.get("evidence_refs") or []),
            "scope_matches_tested_behavior": bool(record.get("scope_matches_tested_behavior", True)),
            "verified_report_coverage": bool(record.get("verified_report_coverage", True)),
            "path_exists": bool(record.get("path_exists", bool(record.get("path")))),
        },
    }


def _findings_for(linkage: dict[str, Any], source_ref: str) -> list[AcceptanceFinding]:
    findings: list[AcceptanceFinding] = []
    record = linkage["acceptance_record"]
    if linkage["task_status"] == "done" and not record["path"] and not linkage["exception_reason"]:
        findings.append(_finding("done_task_missing_acceptance", "Done task requires acceptance record or exception reason.", source_ref))
        return findings
    if not record["path"]:
        return findings

    if not AC_PATH_PATTERN.match(record["path"]):
        findings.append(_finding("acceptance_record_path_invalid", "Acceptance record path must be canonical.", source_ref))
    if not record["path_exists"]:
        findings.append(_finding("acceptance_record_missing", "Acceptance record path must exist or be explicitly generated.", source_ref))
    if record["state"] not in ACCEPTANCE_STATES:
        findings.append(_finding("acceptance_state_invalid", "Acceptance record state must be accepted, conditionally_accepted, or held.", source_ref))
    missing_headings = sorted(REQUIRED_HEADINGS - set(record["headings"]))
    if missing_headings:
        findings.append(_finding(
            "acceptance_required_heading_missing",
            f"Acceptance record headings missing: {', '.join(missing_headings)}",
            source_ref,
        ))
    if not record["scope_matches_tested_behavior"]:
        findings.append(_finding(
            "acceptance_scope_too_broad",
            "Acceptance record scope must not exceed tested behavior.",
            source_ref,
        ))
    if record["evidence_refs"] and not record["verified_report_coverage"]:
        findings.append(_finding(
            "acceptance_report_coverage_unverified",
            "Acceptance record cites report without verifying requirement coverage.",
            source_ref,
        ))
    if linkage["task_status"] == "done" and record["state"] == "held" and not linkage["exception_reason"]:
        findings.append(_finding(
            "done_task_acceptance_held_without_exception",
            "Done task with held acceptance requires exception reason.",
            source_ref,
        ))
    return findings


def _finding(code: str, message: str, source_ref: str) -> AcceptanceFinding:
    return AcceptanceFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
    )
