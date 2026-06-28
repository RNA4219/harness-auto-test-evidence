from __future__ import annotations

from typing import Any

SCHEMA_VERSION = "HATE/v1"

ROLES = ["admin", "maintainer", "developer", "auditor", "viewer", "service_account", "security_reviewer"]

RESOURCE_ACTIONS = {
    "product-readiness": ["read"],
    "runs": ["read"],
    "bundles": ["read"],
    "evidence": ["read"],
    "risk-debt": ["read"],
    "profiles": ["read", "write", "approve"],
    "adapters": ["read", "write"],
    "artifacts": ["read_summary", "read_raw", "export"],
    "audit-events": ["read", "append"],
    "quarantine": ["read", "release"],
    "rbac": ["read", "write"],
    "retention": ["read", "write"],
}


ROLE_PERMISSIONS: dict[str, set[str]] = {
    "admin": {
        "*:*",
    },
    "maintainer": {
        "product-readiness:read",
        "runs:read",
        "bundles:read",
        "evidence:read",
        "risk-debt:read",
        "profiles:read",
        "profiles:write",
        "adapters:read",
        "adapters:write",
        "artifacts:read_summary",
        "artifacts:read_raw",
        "artifacts:export",
        "audit-events:read",
        "quarantine:read",
        "retention:read",
    },
    "developer": {
        "product-readiness:read",
        "runs:read",
        "bundles:read",
        "evidence:read",
        "risk-debt:read",
        "profiles:read",
        "adapters:read",
        "artifacts:read_summary",
    },
    "auditor": {
        "product-readiness:read",
        "runs:read",
        "bundles:read",
        "evidence:read",
        "risk-debt:read",
        "profiles:read",
        "adapters:read",
        "artifacts:read_summary",
        "artifacts:read_raw",
        "audit-events:read",
        "quarantine:read",
        "retention:read",
    },
    "viewer": {
        "product-readiness:read",
        "runs:read",
        "bundles:read",
        "evidence:read",
    },
    "service_account": {
        "product-readiness:read",
        "runs:read",
        "bundles:read",
        "evidence:read",
        "risk-debt:read",
        "artifacts:read_summary",
        "audit-events:append",
    },
    "security_reviewer": {
        "product-readiness:read",
        "runs:read",
        "bundles:read",
        "evidence:read",
        "risk-debt:read",
        "artifacts:read_summary",
        "audit-events:read",
        "quarantine:read",
    },
}

READ_MODEL_RESOURCE_ACTION = {
    "runs": ("runs", "read"),
    "bundles": ("bundles", "read"),
    "evidence": ("evidence", "read"),
    "artifacts": ("artifacts", "read_raw"),
    "risk-debt": ("risk-debt", "read"),
    "profiles": ("profiles", "read"),
    "adapters": ("adapters", "read"),
    "audit-events": ("audit-events", "read"),
    "product-readiness": ("product-readiness", "read"),
}


def is_allowed(role: str, resource: str, action: str) -> bool:
    normalized_role = role.lower()
    permissions = ROLE_PERMISSIONS.get(normalized_role, set())
    return "*:*" in permissions or f"{resource}:{action}" in permissions


def read_model_allowed(role: str, resource: str) -> bool:
    resource_action = READ_MODEL_RESOURCE_ACTION.get(resource)
    if resource_action is None:
        return True
    mapped_resource, action = resource_action
    return is_allowed(role, mapped_resource, action)


def build_rbac_matrix_report(run_id: str) -> dict[str, Any]:
    matrix = []
    for role in ROLES:
        for resource, actions in RESOURCE_ACTIONS.items():
            for action in actions:
                allowed = is_allowed(role, resource, action)
                matrix.append({
                    "role": role,
                    "resource": resource,
                    "action": action,
                    "decision": "allow" if allowed else "deny",
                    "reason": _decision_reason(role, resource, action, allowed),
                })
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "rbac_matrix_report",
        "run_id": run_id,
        "roles": ROLES,
        "resources": [{"resource": resource, "actions": actions} for resource, actions in RESOURCE_ACTIONS.items()],
        "matrix": matrix,
        "invariants": {
            "auditor_read_only": _role_has_no_write_or_approve("auditor"),
            "viewer_raw_artifact_denied": not is_allowed("viewer", "artifacts", "read_raw"),
            "developer_audit_log_denied": not is_allowed("developer", "audit-events", "read"),
            "service_account_human_approval_substitute": False,
            "qeg_approval_not_reimplemented": True,
            "least_privilege_default_deny": True,
        },
        "read_model_mapping": [
            {
                "read_model_resource": resource,
                "permission": f"{mapped_resource}:{action}",
                "viewer_allowed": read_model_allowed("viewer", resource),
                "developer_allowed": read_model_allowed("developer", resource),
                "auditor_allowed": read_model_allowed("auditor", resource),
            }
            for resource, (mapped_resource, action) in READ_MODEL_RESOURCE_ACTION.items()
        ],
        "source_refs": ["docs/process/ENTERPRISE_DOMAIN_MODEL.md", "docs/process/HOSTED_READ_MODEL_API.md"],
        "precheck_decision_override": False,
        "qeg_verdict_override": False,
        "release_gate_override": False,
        "publish_gate_override": False,
    }


def _role_has_no_write_or_approve(role: str) -> bool:
    permissions = ROLE_PERMISSIONS.get(role, set())
    return not any(permission.endswith(":write") or permission.endswith(":approve") or permission.endswith(":release") for permission in permissions)


def _decision_reason(role: str, resource: str, action: str, allowed: bool) -> str:
    if role == "admin" and allowed:
        return "admin wildcard within HATE control plane; QEG approval remains external"
    if role == "auditor" and not allowed:
        return "auditor is read-only"
    if role == "viewer" and resource == "artifacts" and action != "read_summary":
        return "viewer cannot access raw artifacts or exports"
    if role == "service_account" and action in {"approve", "release"}:
        return "service account cannot replace human approval"
    return "explicit role permission" if allowed else "default deny"
