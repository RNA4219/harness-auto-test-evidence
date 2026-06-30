"""Artifact lifecycle state machine for HATE-GAP-016."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


VALID_STATES = {"safe", "quarantined", "released", "deleted", "blocked"}
VALID_ACTIONS = {"retain", "quarantine", "release", "delete"}


@dataclass(frozen=True)
class ArtifactLifecycleFinding:
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


def evaluate_artifact_lifecycle_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_artifact_lifecycle_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "artifact-lifecycle-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_artifact_lifecycle_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "artifact-lifecycle-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["artifact-lifecycle"])
    transitions = [_transition_for(item, source_refs[0]) for item in _normalize_items(input_data)]
    findings = [finding for transition in transitions for finding in transition["findings"]]
    status = "hold" if findings else "pass"

    return {
        "schema_version": "HATE/v1",
        "record_type": "artifact-lifecycle-report",
        "report_id": report_id,
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "transitions": transitions,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "transition_count": len(transitions),
            "finding_count": len(findings),
            "quarantined_count": sum(1 for item in transitions if item["target_state"] == "quarantined"),
            "deleted_count": sum(1 for item in transitions if item["target_state"] == "deleted"),
            "legal_hold_block_count": sum(
                1 for item in transitions for finding in item["findings"]
                if finding.code == "artifact_legal_hold_delete_denied"
            ),
        },
        "sourceRefs": sorted(set(source_refs)),
    }


def _normalize_items(input_data: dict[str, Any]) -> list[dict[str, Any]]:
    raw_items = input_data.get("artifacts")
    if isinstance(raw_items, list):
        return [_normalize_item(item) for item in raw_items if isinstance(item, dict)]
    return [_normalize_item(input_data)]


def _normalize_item(raw: dict[str, Any]) -> dict[str, Any]:
    state = str(raw.get("artifact_state") or raw.get("state") or "safe")
    action = str(raw.get("action") or _default_action_for(raw))
    return {
        "artifact_id": str(raw.get("artifact_id") or "artifact-default"),
        "artifact_state": state,
        "action": action,
        "retention_class": str(raw.get("retention_class") or "standard"),
        "legal_hold": bool(raw.get("legal_hold", False)),
        "quarantine_reason": str(raw.get("quarantine_reason") or ""),
        "release_actor": str(raw.get("release_actor") or ""),
        "release_reason": str(raw.get("release_reason") or ""),
        "redaction_status": str(raw.get("redaction_status") or "not_required"),
        "sourceRefs": list(raw.get("sourceRefs") or []),
    }


def _default_action_for(raw: dict[str, Any]) -> str:
    state = str(raw.get("artifact_state") or raw.get("state") or "safe")
    if state == "quarantined":
        return "quarantine"
    return "retain"


def _transition_for(item: dict[str, Any], source_ref: str) -> dict[str, Any]:
    findings = _findings_for(item, source_ref)
    target_state = _target_state_for(item, findings)
    return {
        "artifact_id": item["artifact_id"],
        "source_state": item["artifact_state"],
        "action": item["action"],
        "target_state": target_state,
        "retention_class": item["retention_class"],
        "legal_hold": item["legal_hold"],
        "quarantine_required": target_state == "quarantined",
        "delete_allowed": target_state == "deleted",
        "safe_for_summary": target_state in {"safe", "released"},
        "findings": findings,
        "sourceRefs": sorted(set([source_ref] + item["sourceRefs"])),
    }


def _findings_for(item: dict[str, Any], source_ref: str) -> list[ArtifactLifecycleFinding]:
    findings: list[ArtifactLifecycleFinding] = []
    if item["artifact_state"] not in VALID_STATES:
        findings.append(ArtifactLifecycleFinding(
            code="artifact_lifecycle_unknown_state",
            severity="high",
            message=f"Unknown artifact lifecycle state: {item['artifact_state']}",
            sourceRef=source_ref,
        ))
    if item["action"] not in VALID_ACTIONS:
        findings.append(ArtifactLifecycleFinding(
            code="artifact_lifecycle_unknown_action",
            severity="high",
            message=f"Unknown artifact lifecycle action: {item['action']}",
            sourceRef=source_ref,
        ))
    if item["action"] == "delete" and item["legal_hold"]:
        findings.append(ArtifactLifecycleFinding(
            code="artifact_legal_hold_delete_denied",
            severity="high",
            message="Artifact delete is denied while legal hold is active.",
            sourceRef=source_ref,
        ))
    if item["action"] == "release" and item["artifact_state"] != "quarantined":
        findings.append(ArtifactLifecycleFinding(
            code="artifact_release_requires_quarantine",
            severity="medium",
            message="Artifact release is only valid from quarantined state.",
            sourceRef=source_ref,
        ))
    if item["action"] == "release" and (not item["release_actor"] or not item["release_reason"]):
        findings.append(ArtifactLifecycleFinding(
            code="artifact_release_review_missing",
            severity="high",
            message="Released artifacts require actor and reason.",
            sourceRef=source_ref,
        ))
    if item["action"] == "quarantine" and not item["quarantine_reason"] and item["artifact_state"] != "quarantined":
        findings.append(ArtifactLifecycleFinding(
            code="artifact_quarantine_reason_missing",
            severity="medium",
            message="New quarantine transitions require a reason.",
            sourceRef=source_ref,
        ))
    return findings


def _target_state_for(item: dict[str, Any], findings: list[ArtifactLifecycleFinding]) -> str:
    if any(finding.code == "artifact_legal_hold_delete_denied" for finding in findings):
        return "blocked"
    if findings:
        return item["artifact_state"] if item["artifact_state"] in VALID_STATES else "blocked"
    if item["action"] == "delete":
        return "deleted"
    if item["action"] == "quarantine":
        return "quarantined"
    if item["action"] == "release":
        return "released"
    return item["artifact_state"]
