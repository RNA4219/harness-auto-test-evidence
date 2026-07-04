from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .common import apply_productization_contract_tree, productization_envelope


APPROVED_COMPARISON_STATES = {"approved", "frozen", "superseded"}


@dataclass(frozen=True)
class BaselineFinding:
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


def evaluate_baseline_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_baseline_promotion_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "baseline-promotion-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_baseline_promotion_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "baseline-promotion-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["baseline-promotion"])
    baseline = _normalize_baseline(input_data.get("baseline", input_data))
    events = [_normalize_event(event) for event in input_data.get("events", [])]
    (
        final_baseline,
        promotion_requests,
        promotion_decisions,
        immutability_events,
        findings,
    ) = _reduce_events(baseline, events, source_refs[0])

    if final_baseline["comparison_requested"] and final_baseline["state"] not in APPROVED_COMPARISON_STATES:
        findings.append(_finding(
            "baseline_unapproved_for_comparison",
            "Comparison requested against a baseline that is not approved, frozen, or superseded.",
            source_refs[0],
        ))

    status = "hold" if findings else "pass"
    report = {
        "schema_version": "HATE/v1",
        "record_type": "baseline-promotion-report",
        "report_id": report_id,
        **productization_envelope(input_data, report_id=report_id, source_refs=source_refs),
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "baseline_state": final_baseline,
        "promotion_requests": promotion_requests,
        "promotion_decisions": promotion_decisions,
        "immutability_events": immutability_events,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "event_count": len(events),
            "request_count": len(promotion_requests),
            "decision_count": len(promotion_decisions),
            "immutability_event_count": len(immutability_events),
            "finding_count": len(findings),
            "final_state": final_baseline["state"],
            "comparison_allowed": final_baseline["state"] in APPROVED_COMPARISON_STATES and not findings,
        },
        "sourceRefs": sorted(set(source_refs)),
    }
    return apply_productization_contract_tree(report, source_refs=source_refs)


def build_baseline_review_packet(
    input_data: dict[str, Any],
    *,
    packet_id: str = "baseline-review-packet",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["baseline-review-packet"])
    report = (
        input_data
        if input_data.get("record_type") == "baseline-promotion-report"
        else build_baseline_promotion_report(input_data, report_id=f"{packet_id}:promotion", source_refs=source_refs)
    )
    baseline = dict(report.get("baseline_state", {}))
    comparison = _normalize_review_comparison(input_data.get("comparison", {}))
    review_items = _baseline_review_items(baseline, report, comparison)
    findings = _review_packet_findings(baseline, report, review_items, source_refs[0])
    packet = {
        "schema_version": "HATE/v1",
        "record_type": "baseline-review-packet",
        "packet_id": packet_id,
        **productization_envelope(input_data, report_id=packet_id, source_refs=source_refs),
        "readiness_effect": "hold" if findings else "none",
        "baseline_id": baseline.get("baseline_id", ""),
        "repo_id": baseline.get("repo_id", ""),
        "suite_id": baseline.get("suite_id", ""),
        "candidate_run_id": baseline.get("candidate_run_id", ""),
        "reviewer": baseline.get("reviewer", ""),
        "promotion_report_ref": str(report.get("report_id") or ""),
        "comparison": comparison,
        "review_items": review_items,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "review_item_count": len(review_items),
            "required_item_count": sum(1 for item in review_items if item["required"]),
            "satisfied_required_count": sum(1 for item in review_items if item["required"] and item["status"] == "satisfied"),
            "finding_count": len(findings),
            "score_delta": comparison["score_delta"],
            "regression_count_delta": comparison["regression_count_delta"],
            "ready_for_review": not findings and all(item["status"] == "satisfied" for item in review_items if item["required"]),
        },
        "sourceRefs": sorted(set(source_refs + list(report.get("sourceRefs", [])))),
    }
    return apply_productization_contract_tree(packet, source_refs=source_refs)


def write_baseline_review_packet(packet: dict[str, Any], out_path: str | Path) -> dict[str, Any]:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    apply_productization_contract_tree(packet, source_refs=list(packet.get("sourceRefs", [])))
    path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return {
        "schema_version": "HATE/v1",
        "record_type": "baseline-review-packet-artifact",
        **productization_envelope(packet, report_id=f"{packet.get('packet_id') or 'baseline-review-packet'}:artifact", source_refs=list(packet.get("sourceRefs", []))),
        "readiness_effect": str(packet.get("readiness_effect") or "none"),
        "artifact_path": str(path),
        "baseline_id": str(packet.get("baseline_id") or ""),
        "review_item_count": len(packet.get("review_items", [])),
        "sourceRefs": list(packet.get("sourceRefs", [])),
    }


def _normalize_review_comparison(raw: dict[str, Any]) -> dict[str, Any]:
    comparison = dict(raw or {})
    previous_score = _optional_float(comparison.get("previous_score"))
    candidate_score = _optional_float(comparison.get("candidate_score"))
    previous_regressions = int(comparison.get("previous_regression_count") or 0)
    candidate_regressions = int(comparison.get("candidate_regression_count") or 0)
    score_delta = None if previous_score is None or candidate_score is None else round(candidate_score - previous_score, 4)
    return {
        "record_type": "baseline-review-comparison",
        "previous_baseline_ref": str(comparison.get("previous_baseline_ref") or ""),
        "previous_score": previous_score,
        "candidate_score": candidate_score,
        "score_delta": score_delta,
        "previous_regression_count": previous_regressions,
        "candidate_regression_count": candidate_regressions,
        "regression_count_delta": candidate_regressions - previous_regressions,
        "comparison_artifact_ref": str(comparison.get("comparison_artifact_ref") or ""),
    }


def _baseline_review_items(
    baseline: dict[str, Any],
    report: dict[str, Any],
    comparison: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        _review_item("candidate_evidence", bool(baseline.get("candidate_run_id") and baseline.get("evidence_refs")), "Candidate run and evidence refs must be present."),
        _review_item("reviewer_separation", bool(baseline.get("reviewer") and baseline.get("reviewer") != baseline.get("actor")), "Reviewer must be present and separate from actor."),
        _review_item("policy_hash", bool(baseline.get("policy_hash")), "Policy hash must bind the promotion decision."),
        _review_item("expiry", bool(baseline.get("expires_at")), "Baseline must carry an expiry date."),
        _review_item("immutability", bool(baseline.get("immutability_hash") or report.get("immutability_events")), "Immutable before/after state must be visible."),
        _review_item("comparison_artifact", bool(comparison.get("comparison_artifact_ref")), "Reviewer needs comparison artifact for delta inspection."),
        _review_item("regression_delta", comparison.get("regression_count_delta", 0) <= 0, "Candidate must not add unexplained regressions."),
    ]


def _review_item(item_id: str, satisfied: bool, description: str) -> dict[str, Any]:
    return {
        "record_type": "baseline-review-item",
        "item_id": item_id,
        "required": True,
        "status": "satisfied" if satisfied else "missing",
        "description": description,
    }


def _review_packet_findings(
    baseline: dict[str, Any],
    report: dict[str, Any],
    review_items: list[dict[str, Any]],
    source_ref: str,
) -> list[BaselineFinding]:
    findings = [
        _finding("baseline_review_item_missing", f"Baseline review item missing: {item['item_id']}.", source_ref)
        for item in review_items
        if item["required"] and item["status"] != "satisfied"
    ]
    if report.get("findings"):
        findings.append(_finding("baseline_review_blocked_by_promotion_findings", "Review packet cannot be ready while promotion report has findings.", source_ref))
    if baseline.get("state") in {"expired", "revoked", "rejected"}:
        findings.append(_finding("baseline_unapproved_for_comparison", "Rejected, revoked, or expired baseline cannot be review-ready.", source_ref))
    return findings


def _normalize_baseline(raw: dict[str, Any]) -> dict[str, Any]:
    baseline = dict(raw or {})
    return {
        "record_type": "baseline-state",
        "baseline_id": str(baseline.get("baseline_id") or ""),
        "repo_id": str(baseline.get("repo_id") or ""),
        "suite_id": str(baseline.get("suite_id") or ""),
        "candidate_run_id": str(baseline.get("candidate_run_id") or ""),
        "actor": str(baseline.get("actor") or ""),
        "reviewer": str(baseline.get("reviewer") or ""),
        "reason": str(baseline.get("reason") or ""),
        "evidence_refs": [str(item) for item in baseline.get("evidence_refs", [])],
        "policy_hash": str(baseline.get("policy_hash") or ""),
        "expires_at": str(baseline.get("expires_at") or ""),
        "frozen_at": str(baseline.get("frozen_at") or ""),
        "immutability_hash": str(baseline.get("immutability_hash") or ""),
        "previous_baseline_ref": str(baseline.get("previous_baseline_ref") or ""),
        "state": str(baseline.get("state") or "none"),
        "comparison_requested": bool(baseline.get("comparison_requested", False)),
    }


def _normalize_event(raw: dict[str, Any]) -> dict[str, Any]:
    event = dict(raw or {})
    return {
        "event_type": str(event.get("event_type") or ""),
        "actor": str(event.get("actor") or ""),
        "reviewer": str(event.get("reviewer") or ""),
        "reason": str(event.get("reason") or ""),
        "candidate_run_id": str(event.get("candidate_run_id") or ""),
        "evidence_refs": [str(item) for item in event.get("evidence_refs", [])],
        "policy_hash": str(event.get("policy_hash") or ""),
        "expires_at": str(event.get("expires_at") or ""),
        "frozen_at": str(event.get("frozen_at") or ""),
        "immutability_hash": str(event.get("immutability_hash") or ""),
        "previous_baseline_ref": str(event.get("previous_baseline_ref") or ""),
        "sourceRefs": [str(item) for item in event.get("sourceRefs", [])],
    }


def _reduce_events(
    baseline: dict[str, Any],
    events: list[dict[str, Any]],
    source_ref: str,
) -> tuple[list | dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[BaselineFinding]]:
    state = dict(baseline)
    promotion_requests: list[dict[str, Any]] = []
    promotion_decisions: list[dict[str, Any]] = []
    immutability_events: list[dict[str, Any]] = []
    findings: list[BaselineFinding] = []

    for index, event in enumerate(events):
        event_type = event["event_type"]
        event_ref = event["sourceRefs"][0] if event["sourceRefs"] else f"{source_ref}#/events/{index}"
        before_state = state["state"]
        before_hash = state["immutability_hash"]

        _merge_event_fields(state, event)

        if event_type == "proposed":
            if not state["candidate_run_id"] or not state["evidence_refs"]:
                findings.append(_finding(
                    "baseline_candidate_missing_evidence",
                    "Baseline proposal requires candidate_run_id and evidence_refs.",
                    event_ref,
                ))
            state["state"] = "proposed"
            promotion_requests.append(_promotion_request(state, event_ref))
        elif event_type == "approved":
            if not state["reviewer"]:
                findings.append(_finding(
                    "baseline_approval_missing_reviewer",
                    "Baseline approval requires a reviewer.",
                    event_ref,
                ))
            elif state["reviewer"] == state["actor"]:
                findings.append(_finding(
                    "baseline_self_approval_denied",
                    "Baseline approval cannot be performed by the proposal actor.",
                    event_ref,
                ))
            else:
                state["state"] = "approved"
            promotion_decisions.append(_promotion_decision(state, event_type, event_ref))
        elif event_type == "frozen":
            if not state["frozen_at"] or not state["immutability_hash"]:
                findings.append(_finding(
                    "baseline_candidate_missing_evidence",
                    "Frozen baseline requires frozen_at and immutability_hash.",
                    event_ref,
                ))
            else:
                state["state"] = "frozen"
            promotion_decisions.append(_promotion_decision(state, event_type, event_ref))
        elif event_type == "expired":
            state["state"] = "expired"
            findings.append(_finding(
                "baseline_expired",
                "Expired baseline cannot be used to hide regressions.",
                event_ref,
            ))
            promotion_decisions.append(_promotion_decision(state, event_type, event_ref))
        elif event_type == "revoked":
            state["state"] = "revoked"
            findings.append(_finding(
                "baseline_revoked",
                "Revoked baseline cannot be used for comparison.",
                event_ref,
            ))
            promotion_decisions.append(_promotion_decision(state, event_type, event_ref))
        elif event_type == "superseded":
            state["state"] = "superseded"
            promotion_decisions.append(_promotion_decision(state, event_type, event_ref))
        elif event_type == "rejected":
            state["state"] = "rejected"
            promotion_decisions.append(_promotion_decision(state, event_type, event_ref))
        else:
            findings.append(_finding(
                "baseline_unapproved_for_comparison",
                f"Unsupported baseline promotion event: {event_type}.",
                event_ref,
            ))

        immutability_events.append(_immutability_event(state, event_type, before_state, before_hash, event_ref))

    return state, promotion_requests, promotion_decisions, immutability_events, findings


def _merge_event_fields(state: dict[str, Any], event: dict[str, Any]) -> None:
    for key in [
        "actor",
        "reviewer",
        "reason",
        "candidate_run_id",
        "policy_hash",
        "expires_at",
        "frozen_at",
        "immutability_hash",
        "previous_baseline_ref",
    ]:
        if event[key]:
            state[key] = event[key]
    if event["evidence_refs"]:
        state["evidence_refs"] = event["evidence_refs"]


def _promotion_request(state: dict[str, Any], source_ref: str) -> dict[str, Any]:
    return {
        "record_type": "baseline-promotion-request",
        "baseline_id": state["baseline_id"],
        "repo_id": state["repo_id"],
        "suite_id": state["suite_id"],
        "candidate_run_id": state["candidate_run_id"],
        "actor": state["actor"],
        "reason": state["reason"],
        "evidence_refs": state["evidence_refs"],
        "policy_hash": state["policy_hash"],
        "expires_at": state["expires_at"],
        "sourceRefs": [source_ref],
    }


def _promotion_decision(state: dict[str, Any], decision: str, source_ref: str) -> dict[str, Any]:
    return {
        "record_type": "baseline-promotion-decision",
        "baseline_id": state["baseline_id"],
        "decision": decision,
        "actor": state["actor"],
        "reviewer": state["reviewer"],
        "reason": state["reason"],
        "policy_hash": state["policy_hash"],
        "expires_at": state["expires_at"],
        "frozen_at": state["frozen_at"],
        "immutability_hash": state["immutability_hash"],
        "previous_baseline_ref": state["previous_baseline_ref"],
        "sourceRefs": [source_ref],
    }


def _immutability_event(
    state: dict[str, Any],
    event_type: str,
    before_state: str,
    before_hash: str,
    source_ref: str,
) -> dict[str, Any]:
    return {
        "record_type": "baseline-immutability-event",
        "baseline_id": state["baseline_id"],
        "event_type": event_type,
        "before_state": before_state,
        "after_state": state["state"],
        "before_hash": before_hash,
        "after_hash": state["immutability_hash"],
        "sourceRefs": [source_ref],
    }


def _finding(code: str, message: str, source_ref: str) -> BaselineFinding:
    return BaselineFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
        readiness_effect="hold",
    )


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)
