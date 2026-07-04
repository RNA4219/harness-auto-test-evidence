from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .common import apply_productization_contract_tree, productization_envelope


@dataclass(frozen=True)
class HumanReviewFinding:
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


def evaluate_human_review_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_human_review_workflow_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "human-review-workflow-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_human_review_workflow_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "human-review-workflow-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["human-review-workflow"])
    review = _normalize_review(input_data.get("review", input_data))
    actions = [_normalize_action(action) for action in input_data.get("actions", [])]
    state, requests, decisions, attachments, findings = _reduce_actions(review, actions, source_refs[0])
    status = "hold" if findings else "pass"
    report = {
        "schema_version": "HATE/v1",
        "record_type": "human-review-workflow-report",
        "report_id": report_id,
        **productization_envelope(input_data, report_id=report_id, source_refs=source_refs),
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "review_state": state,
        "requests": requests,
        "decisions": decisions,
        "attachments": attachments,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "action_count": len(actions),
            "request_count": len(requests),
            "decision_count": len(decisions),
            "attachment_count": len(attachments),
            "finding_count": len(findings),
            "final_status": state["status"],
        },
        "sourceRefs": sorted(set(source_refs)),
    }
    return apply_productization_contract_tree(report, source_refs=source_refs)


def build_human_review_queue_packet(
    input_data: dict[str, Any],
    *,
    packet_id: str = "human-review-queue-packet",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["human-review-queue"])
    report = (
        input_data
        if input_data.get("record_type") == "human-review-workflow-report"
        else build_human_review_workflow_report(input_data, report_id=f"{packet_id}:workflow", source_refs=source_refs)
    )
    state = dict(report.get("review_state", {}))
    queue_item = _queue_item_for(state, report)
    findings = _queue_packet_findings(report, queue_item, source_refs[0])
    packet = {
        "schema_version": "HATE/v1",
        "record_type": "human-review-queue-packet",
        "packet_id": packet_id,
        **productization_envelope(input_data, report_id=packet_id, source_refs=source_refs),
        "readiness_effect": "hold" if findings else "none",
        "queue_item": queue_item,
        "allowed_actions": _allowed_actions_for(state),
        "evidence_refs": list(state.get("evidence_refs", [])),
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "ready_for_queue": not findings,
            "allowed_action_count": len(_allowed_actions_for(state)),
            "evidence_ref_count": len(state.get("evidence_refs", [])),
            "finding_count": len(findings),
            "status": state.get("status", ""),
        },
        "sourceRefs": sorted(set(source_refs + list(report.get("sourceRefs", [])))),
    }
    return apply_productization_contract_tree(packet, source_refs=source_refs)


def write_human_review_queue_packet(packet: dict[str, Any], out_path: str | Path) -> dict[str, Any]:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    apply_productization_contract_tree(packet, source_refs=list(packet.get("sourceRefs", [])))
    path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return {
        "schema_version": "HATE/v1",
        "record_type": "human-review-queue-packet-artifact",
        **productization_envelope(packet, report_id=f"{packet.get('packet_id') or 'human-review-queue-packet'}:artifact", source_refs=list(packet.get("sourceRefs", []))),
        "readiness_effect": str(packet.get("readiness_effect") or "none"),
        "artifact_path": str(path),
        "allowed_action_count": len(packet.get("allowed_actions", [])),
        "sourceRefs": list(packet.get("sourceRefs", [])),
    }


def _queue_item_for(state: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_type": "human-review-queue-item",
        "review_id": state.get("review_id", ""),
        "operating_record_id": state.get("operating_record_id", ""),
        "required_decision": state.get("required_decision", ""),
        "reviewer": state.get("reviewer", ""),
        "owner": state.get("owner", ""),
        "due_date": state.get("due_date", ""),
        "expiry_date": state.get("expiry_date", ""),
        "status": state.get("status", ""),
        "decision": state.get("decision", ""),
        "decision_hash": state.get("decision_hash", ""),
        "workflow_report_status": report.get("overall_status", ""),
    }


def _allowed_actions_for(state: dict[str, Any]) -> list[str]:
    status = state.get("status", "")
    if status in {"new", "assigned", "evidence_attached"}:
        actions = ["attach_evidence", "approve", "deny", "expire"]
        if status == "new":
            actions.insert(0, "assign_reviewer")
        return actions
    if status in {"approved", "denied"}:
        return ["resolve", "revoke", "supersede", "replay"]
    if status == "superseded":
        return ["resolve", "replay"]
    return ["replay"] if status == "resolved" else []


def _queue_packet_findings(
    report: dict[str, Any],
    queue_item: dict[str, Any],
    source_ref: str,
) -> list[HumanReviewFinding]:
    findings: list[HumanReviewFinding] = []
    if not queue_item["review_id"] or not queue_item["operating_record_id"]:
        findings.append(_finding("human_review_queue_identity_missing", "Queue packet requires review_id and operating_record_id.", source_ref))
    if not queue_item["reviewer"]:
        findings.append(_finding("human_review_reviewer_missing", "Queue packet requires reviewer before operator handoff.", source_ref))
    if not queue_item["due_date"] or not queue_item["expiry_date"]:
        findings.append(_finding("human_review_queue_sla_missing", "Queue packet requires due_date and expiry_date.", source_ref))
    if report.get("findings"):
        findings.append(_finding("human_review_queue_blocked_by_workflow_findings", "Queue packet cannot be ready while workflow findings remain.", source_ref))
    return findings


def _normalize_review(raw: dict[str, Any]) -> dict[str, Any]:
    review = dict(raw or {})
    return {
        "record_type": "human-review-workflow-state",
        "review_id": str(review.get("review_id") or ""),
        "operating_record_id": str(review.get("operating_record_id") or ""),
        "required_decision": str(review.get("required_decision") or "approve_or_reject"),
        "reviewer": str(review.get("reviewer") or ""),
        "owner": str(review.get("owner") or ""),
        "due_date": str(review.get("due_date") or ""),
        "expiry_date": str(review.get("expiry_date") or ""),
        "decision": str(review.get("decision") or ""),
        "decision_reason": str(review.get("decision_reason") or ""),
        "evidence_refs": [str(item) for item in review.get("evidence_refs", [])],
        "previous_decision_ref": str(review.get("previous_decision_ref") or ""),
        "superseded_by": str(review.get("superseded_by") or ""),
        "decision_hash": str(review.get("decision_hash") or ""),
        "status": str(review.get("status") or "new"),
    }


def _normalize_action(raw: dict[str, Any]) -> dict[str, Any]:
    action = dict(raw or {})
    return {
        "action": str(action.get("action") or ""),
        "reviewer": str(action.get("reviewer") or ""),
        "owner": str(action.get("owner") or ""),
        "decision": str(action.get("decision") or ""),
        "decision_reason": str(action.get("decision_reason") or ""),
        "evidence_refs": [str(item) for item in action.get("evidence_refs", [])],
        "previous_decision_ref": str(action.get("previous_decision_ref") or ""),
        "superseded_by": str(action.get("superseded_by") or ""),
        "decision_hash": str(action.get("decision_hash") or ""),
        "replay_hash": str(action.get("replay_hash") or ""),
        "sourceRefs": [str(item) for item in action.get("sourceRefs", [])],
    }


def _reduce_actions(
    review: dict[str, Any],
    actions: list[dict[str, Any]],
    source_ref: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[HumanReviewFinding]]:
    state = dict(review)
    requests: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    attachments: list[dict[str, Any]] = []
    findings: list[HumanReviewFinding] = []

    for index, action in enumerate(actions):
        kind = action["action"]
        action_ref = action["sourceRefs"][0] if action["sourceRefs"] else f"{source_ref}#/actions/{index}"
        _merge_action(state, action)

        if kind == "assign_reviewer":
            if not state["reviewer"]:
                findings.append(_finding("human_review_reviewer_missing", "Review assignment requires reviewer.", action_ref))
            state["status"] = "assigned"
            requests.append(_request_record(state, action_ref))
        elif kind == "attach_evidence":
            if not state["evidence_refs"]:
                findings.append(_finding("human_review_evidence_missing", "Evidence attachment requires evidence_refs.", action_ref))
            else:
                attachments.append(_attachment_record(state, action_ref))
            state["status"] = "evidence_attached"
        elif kind in {"approve", "deny"}:
            _validate_decision_inputs(state, kind, action_ref, findings)
            state["decision"] = kind
            state["status"] = "approved" if kind == "approve" else "denied"
            decisions.append(_decision_record(state, kind, action_ref))
        elif kind == "revoke":
            state["decision"] = "revoked"
            state["status"] = "revoked"
            findings.append(_finding("human_review_revoked", "Revoked review decision cannot release a hold.", action_ref))
            decisions.append(_decision_record(state, kind, action_ref))
        elif kind == "expire":
            state["status"] = "expired"
            findings.append(_finding("human_review_expired", "Expired review decision cannot release a hold.", action_ref))
            decisions.append(_decision_record(state, kind, action_ref))
        elif kind == "supersede":
            state["status"] = "superseded"
            decisions.append(_decision_record(state, kind, action_ref))
        elif kind == "resolve":
            if state["status"] not in {"approved", "denied", "superseded"}:
                findings.append(_finding("human_review_evidence_missing", "Resolve requires a current decision.", action_ref))
            state["status"] = "resolved"
        elif kind == "replay":
            if action["replay_hash"] != state["decision_hash"]:
                findings.append(_finding("human_review_replay_mismatch", "Replay hash differs from decision hash.", action_ref))
        else:
            findings.append(_finding("human_review_evidence_missing", f"Unsupported human review action: {kind}.", action_ref))

    return state, requests, decisions, attachments, findings


def _merge_action(state: dict[str, Any], action: dict[str, Any]) -> None:
    for key in [
        "reviewer",
        "owner",
        "decision_reason",
        "previous_decision_ref",
        "superseded_by",
        "decision_hash",
    ]:
        if action[key]:
            state[key] = action[key]
    if action["evidence_refs"]:
        state["evidence_refs"] = action["evidence_refs"]


def _validate_decision_inputs(
    state: dict[str, Any],
    decision: str,
    source_ref: str,
    findings: list[HumanReviewFinding],
) -> None:
    if not state["reviewer"]:
        findings.append(_finding("human_review_reviewer_missing", "Decision requires reviewer.", source_ref))
    if not state["evidence_refs"]:
        findings.append(_finding("human_review_evidence_missing", "Decision requires attached evidence.", source_ref))
    if decision == "approve" and state["reviewer"] and state["reviewer"] == state["owner"]:
        findings.append(_finding("human_review_self_approval_denied", "Owner cannot self-approve review.", source_ref))


def _request_record(state: dict[str, Any], source_ref: str) -> dict[str, Any]:
    return {
        "record_type": "human-review-workflow-request",
        "review_id": state["review_id"],
        "operating_record_id": state["operating_record_id"],
        "required_decision": state["required_decision"],
        "reviewer": state["reviewer"],
        "owner": state["owner"],
        "due_date": state["due_date"],
        "expiry_date": state["expiry_date"],
        "sourceRefs": [source_ref],
    }


def _decision_record(state: dict[str, Any], decision: str, source_ref: str) -> dict[str, Any]:
    return {
        "record_type": "human-review-workflow-decision",
        "review_id": state["review_id"],
        "decision": decision,
        "decision_reason": state["decision_reason"],
        "reviewer": state["reviewer"],
        "owner": state["owner"],
        "evidence_refs": state["evidence_refs"],
        "previous_decision_ref": state["previous_decision_ref"],
        "superseded_by": state["superseded_by"],
        "decision_hash": state["decision_hash"],
        "sourceRefs": [source_ref],
    }


def _attachment_record(state: dict[str, Any], source_ref: str) -> dict[str, Any]:
    return {
        "record_type": "human-review-evidence-attachment",
        "review_id": state["review_id"],
        "operating_record_id": state["operating_record_id"],
        "evidence_refs": state["evidence_refs"],
        "sourceRefs": [source_ref],
    }


def _finding(code: str, message: str, source_ref: str) -> HumanReviewFinding:
    return HumanReviewFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
        readiness_effect="hold",
    )
