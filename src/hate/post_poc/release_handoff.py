from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .common import apply_productization_contract_tree, productization_envelope


HANDOFF_TARGETS = {"qeg", "shipyard", "agent_state_gate", "agent_gatefield"}
HANDOFF_MODES = {"dry_run", "live_reference", "record_only"}
DENIED_STATUSES = {"denied", "failed", "blocked", "rejected"}


@dataclass(frozen=True)
class ReleaseHandoffFinding:
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


def evaluate_release_handoff_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    report = build_release_handoff_report(
        payload.get("input", {}),
        report_id=str(payload.get("fixture_id") or "release-handoff-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_release_handoff_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "release-handoff-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["release-handoff"])
    request = _normalize_request(input_data.get("request", input_data))
    approval = _approval_reference(input_data.get("approval_reference", {}), request)
    result = _handoff_result(input_data.get("result", {}), request, approval)
    findings = _findings_for(request, approval, result, source_refs[0])
    status = "hold" if findings else "pass"
    report = {
        "schema_version": "HATE/v1",
        "record_type": "release-handoff-report",
        "report_id": report_id,
        **productization_envelope(input_data, report_id=report_id, source_refs=source_refs),
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "handoff_request": request,
        "handoff_result": result,
        "external_approval_reference": approval,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "handoff_target": request["handoff_target"],
            "handoff_mode": request["handoff_mode"],
            "external_status": result["external_status"],
            "external_reference_present": bool(approval["external_run_ref"] and approval["external_decision_ref"]),
            "hate_claimed_final_approval": request["hate_claimed_final_approval"],
            "verdict_overwrite_attempted": request["verdict_overwrite_attempted"],
            "finding_count": len(findings),
        },
        "sourceRefs": sorted(set(source_refs)),
    }
    return apply_productization_contract_tree(report, source_refs=source_refs)


def _normalize_request(raw: dict[str, Any]) -> dict[str, Any]:
    request = dict(raw or {})
    return {
        "record_type": "external-release-handoff-request",
        "handoff_id": str(request.get("handoff_id") or ""),
        "release_candidate_ref": str(request.get("release_candidate_ref") or ""),
        "handoff_target": str(request.get("handoff_target") or ""),
        "handoff_mode": str(request.get("handoff_mode") or "record_only"),
        "external_run_ref": str(request.get("external_run_ref") or ""),
        "external_decision_ref": str(request.get("external_decision_ref") or ""),
        "external_status": str(request.get("external_status") or ""),
        "hate_claimed_final_approval": bool(request.get("hate_claimed_final_approval", False)),
        "verdict_overwrite_attempted": bool(request.get("verdict_overwrite_attempted", False)),
        "target_available": bool(request.get("target_available", True)),
    }


def _approval_reference(raw: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    approval = dict(raw or {})
    return {
        "record_type": "external-approval-reference",
        "handoff_target": str(approval.get("handoff_target") or request["handoff_target"]),
        "external_run_ref": str(approval.get("external_run_ref") or request["external_run_ref"]),
        "external_decision_ref": str(approval.get("external_decision_ref") or request["external_decision_ref"]),
        "external_status": str(approval.get("external_status") or request["external_status"]),
        "authority_owner": str(approval.get("authority_owner") or ""),
    }


def _handoff_result(raw: dict[str, Any], request: dict[str, Any], approval: dict[str, Any]) -> dict[str, Any]:
    result = dict(raw or {})
    return {
        "record_type": "external-release-handoff-result",
        "handoff_id": request["handoff_id"],
        "handoff_target": request["handoff_target"],
        "external_run_ref": str(result.get("external_run_ref") or approval["external_run_ref"]),
        "external_decision_ref": str(result.get("external_decision_ref") or approval["external_decision_ref"]),
        "external_status": str(result.get("external_status") or approval["external_status"]),
        "result_recorded": bool(result.get("result_recorded", True)),
    }


def _findings_for(
    request: dict[str, Any],
    approval: dict[str, Any],
    result: dict[str, Any],
    source_ref: str,
) -> list[ReleaseHandoffFinding]:
    findings: list[ReleaseHandoffFinding] = []
    if request["handoff_target"] not in HANDOFF_TARGETS or request["handoff_mode"] not in HANDOFF_MODES or not request["target_available"]:
        findings.append(_finding("handoff_target_unavailable", "External release handoff target or mode is unavailable.", source_ref))
    if not approval["external_run_ref"] or not approval["external_decision_ref"] or not result["external_run_ref"] or not result["external_decision_ref"]:
        findings.append(_finding("handoff_external_reference_missing", "External run and decision references are required.", source_ref))
    if result["external_status"] in DENIED_STATUSES or approval["external_status"] in DENIED_STATUSES:
        findings.append(_finding("handoff_external_denied", "External release authority denied or blocked the handoff.", source_ref))
    if request["hate_claimed_final_approval"]:
        findings.append(_finding("handoff_hate_claimed_final_approval", "HATE must not claim final release approval.", source_ref))
    if request["verdict_overwrite_attempted"]:
        findings.append(_finding("handoff_verdict_overwrite_attempted", "HATE must preserve external verdicts without overwrite.", source_ref))
    return findings


def _finding(code: str, message: str, source_ref: str) -> ReleaseHandoffFinding:
    return ReleaseHandoffFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
        readiness_effect="hold",
    )
