from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


POST_POC_RECORD_PREFIXES = (
    "baseline-",
    "capacity-",
    "compliance-",
    "connector-",
    "dashboard-",
    "docs-",
    "external-",
    "control-",
    "history-",
    "hosted-",
    "human-review-",
    "incident-",
    "notification-",
    "plugin-",
    "post-incident-",
    "procurement-",
    "real-repo-",
    "release-",
    "runtime-",
    "slo-",
    "store-",
)


def productization_envelope(
    input_data: dict[str, Any],
    *,
    report_id: str,
    source_refs: list[str],
    default_actor: str = "hate-local",
) -> dict[str, Any]:
    """Return shared post-PoC productization contract fields."""
    actor = str(input_data.get("actor") or "")
    system_actor = str(input_data.get("system_actor") or ("" if actor else default_actor))
    decision_basis = input_data.get("decision_basis") or source_refs
    envelope: dict[str, Any] = {
        "record_id": str(input_data.get("record_id") or report_id),
        "created_at": str(input_data.get("created_at") or _now_utc()),
        "decision_basis": [str(item) for item in decision_basis],
        "unsafe_output_policy": str(input_data.get("unsafe_output_policy") or "redact_unsafe_outputs"),
    }
    if actor:
        envelope["actor"] = actor
    else:
        envelope["system_actor"] = system_actor
    tenant_id = str(input_data.get("tenant_id") or _nested_tenant_id(input_data) or "")
    if tenant_id:
        envelope["tenant_id"] = tenant_id
    return envelope


def apply_productization_contract_tree(
    value: Any,
    *,
    source_refs: list[str],
    default_actor: str = "hate-local",
) -> Any:
    """Recursively add the shared post-PoC contract to nested record dicts."""
    if isinstance(value, list):
        for item in value:
            apply_productization_contract_tree(item, source_refs=source_refs, default_actor=default_actor)
        return value
    if not isinstance(value, dict):
        return value

    local_source_refs = _record_source_refs(value, source_refs)
    record_type = str(value.get("record_type") or "")
    if _is_post_poc_record_type(record_type):
        envelope = productization_envelope(
            value,
            report_id=_record_identity(value, record_type),
            source_refs=local_source_refs,
            default_actor=default_actor,
        )
        for key, item in envelope.items():
            value.setdefault(key, item)
        value.setdefault("readiness_effect", _infer_readiness_effect(value))
        value.setdefault("sourceRefs", local_source_refs)

    for item in value.values():
        apply_productization_contract_tree(item, source_refs=local_source_refs, default_actor=default_actor)
    return value


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _nested_tenant_id(input_data: dict[str, Any]) -> str:
    for key in ("request", "session", "slo"):
        value = input_data.get(key)
        if isinstance(value, dict) and value.get("tenant_id"):
            return str(value["tenant_id"])
    telemetry = input_data.get("telemetry")
    if isinstance(telemetry, list):
        for item in telemetry:
            if isinstance(item, dict) and item.get("tenant_id"):
                return str(item["tenant_id"])
    return ""


def _is_post_poc_record_type(record_type: str) -> bool:
    return record_type.startswith(POST_POC_RECORD_PREFIXES)


def _record_source_refs(record: dict[str, Any], fallback: list[str]) -> list[str]:
    if isinstance(record.get("sourceRefs"), list) and record["sourceRefs"]:
        return [str(item) for item in record["sourceRefs"]]
    if record.get("sourceRef"):
        return [str(record["sourceRef"])]
    return [str(item) for item in fallback]


def _record_identity(record: dict[str, Any], record_type: str) -> str:
    for key in (
        "record_id",
        "report_id",
        "packet_id",
        "manifest_id",
        "plan_id",
        "runbook_id",
        "step_id",
        "event_id",
        "request_id",
        "decision_id",
        "operation_id",
        "entry_id",
        "review_id",
        "baseline_id",
        "plugin_id",
        "connector_id",
        "repo_id",
        "job_id",
        "incident_id",
        "notification_id",
        "control_id",
        "route",
        "path",
    ):
        if record.get(key):
            return f"{record_type}:{record[key]}"
    return record_type or "post-poc-record"


def _infer_readiness_effect(record: dict[str, Any]) -> str:
    status_values = {
        str(record.get("overall_status") or ""),
        str(record.get("status") or ""),
        str(record.get("delivery_status") or ""),
        str(record.get("sync_status") or ""),
        str(record.get("lease_state") or ""),
        str(record.get("restore_status") or ""),
        str(record.get("budget_status") or ""),
        str(record.get("review_status") or ""),
        str(record.get("decision") or ""),
    }
    hold_values = {
        "hold",
        "blocked",
        "failed",
        "dead_lettered",
        "expired",
        "revoked",
        "denied",
        "rejected",
        "exceeded",
        "missing",
    }
    return "hold" if status_values & hold_values else "none"
