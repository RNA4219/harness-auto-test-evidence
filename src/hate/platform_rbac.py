"""Platform RBAC matrix decisions for read model/API/dashboard surfaces."""

from __future__ import annotations

import re
from datetime import date
from typing import Any


ROLES = ["admin", "maintainer", "developer", "auditor", "viewer", "service"]
RESOURCE_ACTIONS: dict[str, set[str]] = {
    "run": {"read", "create", "cancel", "retry"},
    "finding": {"read", "assign", "resolve", "supersede"},
    "risk_debt": {"read", "accept", "revoke", "resolve"},
    "manual_review": {"read", "request", "decide"},
    "policy": {"read", "propose", "approve", "change"},
    "artifact": {"metadata_read", "safe_read", "raw_access", "quarantine_release", "delete"},
    "audit_event": {"read"},
    "scheduler": {"read", "enqueue", "lease", "cancel"},
}
MUTATION_ACTIONS = {
    "create",
    "cancel",
    "retry",
    "assign",
    "resolve",
    "supersede",
    "accept",
    "revoke",
    "request",
    "decide",
    "propose",
    "approve",
    "change",
    "quarantine_release",
    "delete",
    "enqueue",
    "lease",
}
RAW_PATH_PATTERN = re.compile(r"([A-Za-z]:\\|/home/|/Users/|\\\\)")
SECRET_PATTERN = re.compile(r"(secret|token|password|apikey|api_key)", re.IGNORECASE)


def build_platform_rbac_report(data: dict[str, Any], report_id: str = "platform-rbac") -> dict[str, Any]:
    """Evaluate one RBAC request and return an auditable report."""
    request = _normalize_request(data)
    decision = evaluate_platform_rbac(request)
    findings = _report_findings(decision)
    return {
        "schema_version": "HATE/v1",
        "record_type": "platform-rbac-matrix-report",
        "report_id": report_id,
        "overall_status": "hold" if findings else "pass",
        "readiness_effect": "hold" if findings else "none",
        "roles": ROLES,
        "resources": [
            {"resource": resource, "actions": sorted(actions)}
            for resource, actions in RESOURCE_ACTIONS.items()
        ],
        "decision": decision,
        "findings": findings,
        "summary": {
            "decision": decision["decision"],
            "http_status": decision["http_status"],
            "tenant_visible": decision["tenant_visible"],
            "restricted_payload_loaded": decision["restricted_payload_loaded"],
            "finding_count": len(findings),
        },
        "sourceRefs": list(data.get("sourceRefs") or request.get("sourceRefs") or []),
    }


def evaluate_platform_rbac(request: dict[str, Any]) -> dict[str, Any]:
    """Evaluate a single platform RBAC request without loading restricted payloads."""
    actor = dict(request.get("actor") or {})
    resource = dict(request.get("resource") or {})
    artifact = dict(request.get("artifact") or {})
    role = str(actor.get("role") or "viewer")
    action = str(request.get("action") or "read")
    resource_type = str(resource.get("type") or "")
    same_tenant = str(actor.get("tenant_id") or "") == str(resource.get("tenant_id") or "")
    resource_exists = bool(resource.get("exists", True))
    tenant_visible = same_tenant and resource_exists
    restricted_payload_loaded = False

    decision = "deny"
    reason = "role_permission_denied"
    http_status = 403

    if role not in ROLES:
        reason = "unknown_role"
    elif resource_type not in RESOURCE_ACTIONS or action not in RESOURCE_ACTIONS[resource_type]:
        reason = "unknown_resource_action"
    elif not same_tenant:
        reason = "cross_tenant_hidden"
        http_status = 403
    elif not resource_exists:
        reason = "same_tenant_resource_missing"
        http_status = 404
    elif _legal_hold_bypass_attempt(resource, action):
        reason = "legal_hold_bypass_denied"
    elif resource_type == "artifact" and action == "raw_access":
        decision, reason = _raw_artifact_decision(role, artifact)
        http_status = 200 if decision == "allow" else 403
        restricted_payload_loaded = decision == "allow"
    elif _role_allows(role, resource_type, action, request):
        decision = "allow"
        reason = "role_permission_allowed"
        http_status = 200

    denial_record = _denial_record(reason, request) if decision == "deny" else {}
    return {
        "actor_id": str(actor.get("actor_id") or "unknown"),
        "role": role,
        "resource_type": resource_type,
        "resource_id": _safe_resource_id(resource),
        "action": action,
        "decision": decision,
        "reason": reason,
        "http_status": http_status,
        "tenant_visible": tenant_visible,
        "restricted_payload_loaded": restricted_payload_loaded,
        "raw_artifact_returned": decision == "allow" and resource_type == "artifact" and action == "raw_access",
        "denial_record": denial_record,
        "sourceRefs": list(request.get("sourceRefs") or []),
    }


def _normalize_request(data: dict[str, Any]) -> dict[str, Any]:
    if "request" in data:
        request = dict(data["request"])
        request.setdefault("sourceRefs", data.get("sourceRefs", []))
        return request
    return dict(data)


def _role_allows(role: str, resource_type: str, action: str, request: dict[str, Any]) -> bool:
    if role == "admin":
        return not (resource_type == "artifact" and action == "raw_access")
    if role == "maintainer":
        return _maintainer_allows(resource_type, action)
    if role == "developer":
        return _developer_allows(resource_type, action, request)
    if role == "auditor":
        return action == "read" or action in {"metadata_read", "safe_read"}
    if role == "viewer":
        return (resource_type == "run" and action == "read") or (
            resource_type == "artifact" and action in {"metadata_read", "safe_read"}
        )
    if role == "service":
        return _service_allows(resource_type, action, request)
    return False


def _maintainer_allows(resource_type: str, action: str) -> bool:
    if resource_type in {"run", "finding", "risk_debt", "manual_review"}:
        return True
    if resource_type == "policy":
        return action in {"read", "propose"}
    if resource_type == "artifact":
        return action in {"metadata_read", "safe_read", "quarantine_release"}
    if resource_type == "audit_event":
        return action == "read"
    if resource_type == "scheduler":
        return action in {"read", "enqueue", "cancel"}
    return False


def _developer_allows(resource_type: str, action: str, request: dict[str, Any]) -> bool:
    if not bool(request.get("owned_resource", False)):
        return False
    if resource_type == "run":
        return action in {"read", "create"}
    if resource_type == "finding":
        return action in {"read", "assign"}
    if resource_type == "artifact":
        return action in {"metadata_read", "safe_read"}
    return False


def _service_allows(resource_type: str, action: str, request: dict[str, Any]) -> bool:
    delegated = set(request.get("delegated_actions") or [])
    if action in {"decide", "approve", "change", "delete", "quarantine_release"} and action not in delegated:
        return False
    if resource_type == "scheduler":
        return action in {"read", "enqueue", "lease", "cancel"}
    if resource_type == "run":
        return action in {"read", "create", "cancel", "retry"}
    if resource_type == "finding":
        return action in {"read", "assign"}
    if resource_type == "manual_review":
        return action in {"read", "request"} or action in delegated
    return False


def _raw_artifact_decision(role: str, artifact: dict[str, Any]) -> tuple[str, str]:
    if role in {"viewer", "developer"}:
        return "deny", "raw_artifact_role_denied"
    if artifact.get("safety_state") not in {"safe", "approved_raw"}:
        return "deny", "raw_artifact_safety_state_denied"
    if not artifact.get("approval_event_ref"):
        return "deny", "raw_artifact_approval_required"
    if not artifact.get("purpose"):
        return "deny", "raw_artifact_purpose_required"
    if not artifact.get("expiry"):
        return "deny", "raw_artifact_expiry_required"
    if not _expiry_valid(str(artifact.get("expiry"))):
        return "deny", "raw_artifact_expiry_invalid"
    if not artifact.get("audit_event_ref"):
        return "deny", "raw_artifact_audit_event_required"
    return "allow", "raw_artifact_access_approved"


def _expiry_valid(value: str) -> bool:
    try:
        return date.fromisoformat(value) >= date(2026, 7, 1)
    except ValueError:
        return False


def _legal_hold_bypass_attempt(resource: dict[str, Any], action: str) -> bool:
    return bool(resource.get("legal_hold", False)) and action == "delete"


def _safe_resource_id(resource: dict[str, Any]) -> str:
    resource_id = str(resource.get("id") or "")
    if RAW_PATH_PATTERN.search(resource_id) or SECRET_PATTERN.search(resource_id):
        return "redacted"
    return resource_id


def _denial_record(reason: str, request: dict[str, Any]) -> dict[str, Any]:
    resource = dict(request.get("resource") or {})
    return {
        "reason": reason,
        "resource_type": str(resource.get("type") or ""),
        "resource_id": _safe_resource_id(resource),
        "message": f"access denied: {reason}",
    }


def _report_findings(decision: dict[str, Any]) -> list[dict[str, Any]]:
    findings = []
    denial_record = decision.get("denial_record") or {}
    serialized = str(denial_record)
    if RAW_PATH_PATTERN.search(serialized):
        findings.append(_finding("platform_rbac_denial_leaks_raw_path"))
    if SECRET_PATTERN.search(serialized):
        findings.append(_finding("platform_rbac_denial_leaks_secret"))
    if decision["decision"] == "deny" and decision["restricted_payload_loaded"]:
        findings.append(_finding("platform_rbac_payload_loaded_before_authz"))
    if decision["role"] in {"viewer", "developer"} and decision["raw_artifact_returned"]:
        findings.append(_finding("platform_rbac_unsafe_raw_artifact_returned"))
    return findings


def _finding(code: str) -> dict[str, Any]:
    return {
        "code": code,
        "severity": "high",
        "readiness_effect": "hold",
        "message": code,
        "sourceRefs": [],
    }
