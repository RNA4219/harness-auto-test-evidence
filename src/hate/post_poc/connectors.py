from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .common import apply_productization_contract_tree, productization_envelope


MODES = {"dry_run", "live", "replay", "rollback_preview"}


@dataclass(frozen=True)
class ConnectorRuntimeFinding:
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


def evaluate_connector_runtime_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_connector_runtime_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "connector-runtime-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_connector_runtime_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "connector-runtime-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["connector-runtime"])
    plan = _normalize_plan(input_data.get("plan", input_data))
    attempts = [_normalize_attempt(attempt) for attempt in input_data.get("attempts", [])]
    runtime_plan, runtime_attempts, idempotency_records, rollback_records, findings = _reduce_attempts(
        plan,
        attempts,
        source_refs[0],
    )
    status = "hold" if findings else "pass"
    report = {
        "schema_version": "HATE/v1",
        "record_type": "connector-runtime-report",
        "report_id": report_id,
        **productization_envelope(input_data, report_id=report_id, source_refs=source_refs),
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "runtime_plan": runtime_plan,
        "runtime_attempts": runtime_attempts,
        "idempotency_records": idempotency_records,
        "rollback_visibility_records": rollback_records,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "attempt_count": len(runtime_attempts),
            "idempotency_record_count": len(idempotency_records),
            "rollback_visibility_count": len(rollback_records),
            "finding_count": len(findings),
            "mode": runtime_plan["mode"],
            "sync_status": runtime_plan["sync_status"],
            "side_effect_performed": runtime_plan["side_effect_performed"],
        },
        "sourceRefs": sorted(set(source_refs)),
    }
    return apply_productization_contract_tree(report, source_refs=source_refs)


def build_connector_execution_plan(
    input_data: dict[str, Any],
    *,
    plan_id: str = "connector-execution-plan",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["connector-execution-plan"])
    plan = _normalize_plan(input_data.get("plan", input_data))
    steps = _execution_steps_for(plan, source_refs[0])
    findings = _execution_plan_findings(plan, steps, source_refs[0])
    execution_plan = {
        "schema_version": "HATE/v1",
        "record_type": "connector-execution-plan",
        "plan_id": plan_id,
        **productization_envelope(input_data, report_id=plan_id, source_refs=source_refs),
        "readiness_effect": "hold" if findings else "none",
        "connector_id": plan["connector_id"],
        "connector_type": plan["connector_type"],
        "mode": plan["mode"],
        "endpoint_ref": plan["endpoint_ref"],
        "idempotency_key": plan["idempotency_key"],
        "payload_hash": plan["payload_hash"],
        "redaction_report_ref": plan["redaction_report_ref"],
        "approval_required": plan["mode"] == "live",
        "rollback_required": plan["mode"] in {"live", "replay"},
        "steps": steps,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "step_count": len(steps),
            "hold_count": len(findings),
            "execution_allowed": not findings and any(step["step_type"] == "execute" and step["status"] == "ready" for step in steps),
            "rollback_available": plan["rollback_available"],
            "side_effect_possible": plan["mode"] == "live",
        },
        "sourceRefs": sorted(set(source_refs)),
    }
    return apply_productization_contract_tree(execution_plan, source_refs=source_refs)


def write_connector_execution_manifest(plan: dict[str, Any], out_path: str | Path) -> dict[str, Any]:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": "HATE/v1",
        "record_type": "connector-execution-manifest",
        "plan_id": str(plan.get("plan_id") or ""),
        **productization_envelope(plan, report_id=str(plan.get("plan_id") or "connector-execution-manifest"), source_refs=list(plan.get("sourceRefs", []))),
        "readiness_effect": str(plan.get("readiness_effect") or "none"),
        "connector_id": str(plan.get("connector_id") or ""),
        "connector_type": str(plan.get("connector_type") or ""),
        "mode": str(plan.get("mode") or ""),
        "endpoint_ref": str(plan.get("endpoint_ref") or ""),
        "idempotency_key": str(plan.get("idempotency_key") or ""),
        "payload_hash": str(plan.get("payload_hash") or ""),
        "redaction_report_ref": str(plan.get("redaction_report_ref") or ""),
        "steps": list(plan.get("steps", [])),
        "sourceRefs": list(plan.get("sourceRefs", [])),
    }
    apply_productization_contract_tree(manifest, source_refs=manifest["sourceRefs"])
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return {
        "schema_version": "HATE/v1",
        "record_type": "connector-execution-manifest-artifact",
        **productization_envelope(manifest, report_id=f"{manifest['plan_id']}:artifact", source_refs=manifest["sourceRefs"]),
        "readiness_effect": manifest["readiness_effect"],
        "artifact_path": str(path),
        "step_count": len(manifest["steps"]),
        "sourceRefs": manifest["sourceRefs"],
    }


def _execution_steps_for(plan: dict[str, Any], source_ref: str) -> list[dict[str, Any]]:
    steps = [
        _execution_step("validate_plan", "ready", "Validate endpoint, idempotency, token ref, and payload hash.", plan, source_ref),
        _execution_step("redact_payload", "ready" if plan["redaction_report_ref"] else "blocked", "Require redaction report before connector handoff.", plan, source_ref),
        _execution_step("reserve_idempotency", "ready" if plan["idempotency_key"] and plan["payload_hash"] else "blocked", "Reserve idempotency key for retry-safe handoff.", plan, source_ref),
        _execution_step("approval_gate", "ready" if plan["mode"] != "live" or plan["live_mode_allowed"] else "blocked", "Require explicit live-mode approval before side effects.", plan, source_ref),
        _execution_step(
            "execute",
            "ready" if plan["mode"] == "live" and plan["live_mode_allowed"] else "skipped",
            "Execute only when live mode is explicitly approved.",
            plan,
            source_ref,
        ),
        _execution_step("verify_result", "ready", "Verify external_ref and sync status after attempt.", plan, source_ref),
        _execution_step(
            "rollback_preview",
            "ready" if plan["rollback_available"] else "blocked",
            "Record rollback visibility before treating connector result as operable.",
            plan,
            source_ref,
        ),
    ]
    if plan["mode"] in {"dry_run", "rollback_preview"}:
        steps[4]["status"] = "skipped"
    if plan["mode"] == "replay":
        steps[4]["status"] = "skipped"
        steps[5]["description"] = "Replay verifies recorded external_ref and sync status without new side effects."
    return steps


def _execution_step(step_type: str, status: str, description: str, plan: dict[str, Any], source_ref: str) -> dict[str, Any]:
    return {
        "record_type": "connector-execution-step",
        **productization_envelope(plan, report_id=f"connector-execution-step:{step_type}", source_refs=[source_ref]),
        "readiness_effect": "hold" if status == "blocked" else "none",
        "step_type": step_type,
        "status": status,
        "description": description,
        "connector_id": plan["connector_id"],
        "mode": plan["mode"],
        "endpoint_ref": plan["endpoint_ref"],
        "sourceRefs": [source_ref],
    }


def _execution_plan_findings(
    plan: dict[str, Any],
    steps: list[dict[str, Any]],
    source_ref: str,
) -> list[ConnectorRuntimeFinding]:
    findings: list[ConnectorRuntimeFinding] = []
    _validate_plan(plan, source_ref, findings)
    blocked = [step["step_type"] for step in steps if step["status"] == "blocked"]
    if blocked:
        findings.append(_finding(
            "connector_execution_step_blocked",
            f"Connector execution plan has blocked steps: {', '.join(blocked)}.",
            source_ref,
        ))
    if plan["mode"] == "live" and not plan["rollback_available"]:
        findings.append(_finding(
            "connector_rollback_visibility_missing",
            "Live connector execution requires rollback preview before handoff.",
            source_ref,
        ))
    return findings


def _normalize_plan(raw: dict[str, Any]) -> dict[str, Any]:
    plan = dict(raw or {})
    return {
        "record_type": "connector-runtime-plan",
        "connector_id": str(plan.get("connector_id") or ""),
        "connector_type": str(plan.get("connector_type") or ""),
        "mode": str(plan.get("mode") or "dry_run"),
        "endpoint_ref": str(plan.get("endpoint_ref") or ""),
        "endpoint_available": bool(plan.get("endpoint_available", True)),
        "live_mode_allowed": bool(plan.get("live_mode_allowed", False)),
        "idempotency_key": str(plan.get("idempotency_key") or ""),
        "payload_hash": str(plan.get("payload_hash") or ""),
        "redaction_report_ref": str(plan.get("redaction_report_ref") or ""),
        "token_ref": str(plan.get("token_ref") or ""),
        "raw_token": str(plan.get("raw_token") or ""),
        "rollback_available": bool(plan.get("rollback_available", False)),
        "external_ref": str(plan.get("external_ref") or ""),
        "sync_status": str(plan.get("sync_status") or "planned"),
        "side_effect_performed": bool(plan.get("side_effect_performed", False)),
    }


def _normalize_attempt(raw: dict[str, Any]) -> dict[str, Any]:
    attempt = dict(raw or {})
    return {
        "attempt": int(attempt.get("attempt") or 1),
        "mode": str(attempt.get("mode") or ""),
        "sync_status": str(attempt.get("sync_status") or ""),
        "external_ref": str(attempt.get("external_ref") or ""),
        "error_code": str(attempt.get("error_code") or ""),
        "side_effect_performed": bool(attempt.get("side_effect_performed", False)),
        "sourceRefs": [str(item) for item in attempt.get("sourceRefs", [])],
    }


def _reduce_attempts(
    plan: dict[str, Any],
    attempts: list[dict[str, Any]],
    source_ref: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[ConnectorRuntimeFinding]]:
    state = dict(plan)
    runtime_attempts: list[dict[str, Any]] = []
    idempotency_records: list[dict[str, Any]] = []
    rollback_records: list[dict[str, Any]] = []
    findings: list[ConnectorRuntimeFinding] = []
    _validate_plan(state, source_ref, findings)

    for index, attempt in enumerate(attempts):
        attempt_ref = attempt["sourceRefs"][0] if attempt["sourceRefs"] else f"{source_ref}#/attempts/{index}"
        _merge_attempt(state, attempt)
        runtime_attempts.append(_attempt_record(state, attempt_ref))
        idempotency_records.append(_idempotency_record(state, attempt_ref))
        rollback_records.append(_rollback_record(state, attempt_ref))
        if state["mode"] == "dry_run" and state["side_effect_performed"]:
            findings.append(_finding("connector_live_mode_not_allowed", "Dry-run connector attempts must not perform side effects.", attempt_ref))

    if not attempts:
        idempotency_records.append(_idempotency_record(state, source_ref))
        rollback_records.append(_rollback_record(state, source_ref))

    if not state["rollback_available"]:
        findings.append(_finding(
            "connector_rollback_visibility_missing",
            "Connector runtime requires rollback visibility for live or replayable operations.",
            source_ref,
        ))
    if state["sync_status"] in {"failed", "rejected"}:
        findings.append(_finding("connector_payload_rejected", "Connector payload was rejected by endpoint.", source_ref))

    return state, runtime_attempts, idempotency_records, rollback_records, findings


def _validate_plan(plan: dict[str, Any], source_ref: str, findings: list[ConnectorRuntimeFinding]) -> None:
    if plan["mode"] not in MODES:
        findings.append(_finding("connector_live_mode_not_allowed", "Unsupported connector runtime mode.", source_ref))
    if plan["mode"] == "live" and not plan["live_mode_allowed"]:
        findings.append(_finding("connector_live_mode_not_allowed", "Live connector mode requires explicit fake/live allowance.", source_ref))
    if plan["raw_token"] or (plan["token_ref"] and not plan["token_ref"].startswith(("secret-ref://", "token-ref://"))):
        findings.append(_finding("connector_token_exposed", "Connector runtime must use token_ref and never expose raw tokens.", source_ref))
    if not plan["idempotency_key"] or not plan["payload_hash"]:
        findings.append(_finding("connector_idempotency_key_missing", "Connector runtime requires idempotency_key and payload_hash.", source_ref))
    if not plan["endpoint_ref"] or not plan["endpoint_available"]:
        findings.append(_finding("connector_endpoint_unavailable", "Connector endpoint must be available and represented by endpoint_ref.", source_ref))
    if not plan["redaction_report_ref"]:
        findings.append(_finding("connector_payload_rejected", "Connector payload requires redaction_report_ref.", source_ref))


def _merge_attempt(state: dict[str, Any], attempt: dict[str, Any]) -> None:
    for key in ["mode", "sync_status", "external_ref", "error_code"]:
        if attempt[key]:
            state[key] = attempt[key]
    if attempt["side_effect_performed"]:
        state["side_effect_performed"] = True


def _attempt_record(state: dict[str, Any], source_ref: str) -> dict[str, Any]:
    return {
        "record_type": "connector-runtime-attempt",
        "connector_id": state["connector_id"],
        "connector_type": state["connector_type"],
        "mode": state["mode"],
        "endpoint_ref": state["endpoint_ref"],
        "external_ref": state["external_ref"],
        "sync_status": state["sync_status"],
        "payload_hash": state["payload_hash"],
        "redaction_report_ref": state["redaction_report_ref"],
        "side_effect_performed": state["side_effect_performed"],
        "sourceRefs": [source_ref],
    }


def _idempotency_record(state: dict[str, Any], source_ref: str) -> dict[str, Any]:
    return {
        "record_type": "connector-idempotency-record",
        "connector_id": state["connector_id"],
        "idempotency_key": state["idempotency_key"],
        "payload_hash": state["payload_hash"],
        "external_ref": state["external_ref"],
        "sync_status": state["sync_status"],
        "sourceRefs": [source_ref],
    }


def _rollback_record(state: dict[str, Any], source_ref: str) -> dict[str, Any]:
    return {
        "record_type": "connector-rollback-visibility-record",
        "connector_id": state["connector_id"],
        "external_ref": state["external_ref"],
        "rollback_available": state["rollback_available"],
        "mode": state["mode"],
        "sync_status": state["sync_status"],
        "sourceRefs": [source_ref],
    }


def _finding(code: str, message: str, source_ref: str) -> ConnectorRuntimeFinding:
    return ConnectorRuntimeFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
        readiness_effect="hold",
    )
