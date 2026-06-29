"""Enterprise RBAC projection for local HATE resources.

The module intentionally produces local, auditable decisions only. It never
mutates readiness verdicts, artifact manifests, or stored reports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


READ_ACTIONS = {"read"}
EXPORT_ACTIONS = {"export"}
REVIEW_ACTIONS = {"review", "approve_review", "reject_review"}
QUARANTINE_ACTIONS = {"quarantine", "release_quarantine"}
ADMIN_ACTIONS = {"admin", "configure_policy", "manage_role", "delete_resource"}

RESOURCE_TYPES = {"run", "artifact", "report", "manual_review", "export", "admin", "audit"}

ROLE_PERMISSIONS: dict[str, dict[str, set[str]]] = {
    "admin": {
        "*": READ_ACTIONS | EXPORT_ACTIONS | REVIEW_ACTIONS | QUARANTINE_ACTIONS | ADMIN_ACTIONS,
    },
    "maintainer": {
        "run": READ_ACTIONS,
        "report": READ_ACTIONS,
        "artifact": READ_ACTIONS,
        "manual_review": READ_ACTIONS | REVIEW_ACTIONS,
        "export": EXPORT_ACTIONS,
        "audit": READ_ACTIONS,
    },
    "reviewer": {
        "run": READ_ACTIONS,
        "report": READ_ACTIONS,
        "artifact": READ_ACTIONS,
        "manual_review": READ_ACTIONS | REVIEW_ACTIONS,
        "audit": READ_ACTIONS,
    },
    "auditor": {
        "run": READ_ACTIONS,
        "report": READ_ACTIONS,
        "artifact": READ_ACTIONS,
        "manual_review": READ_ACTIONS,
        "audit": READ_ACTIONS,
        "export": EXPORT_ACTIONS,
    },
    "viewer": {
        "run": READ_ACTIONS,
        "report": READ_ACTIONS,
        "artifact": READ_ACTIONS,
    },
}

CLASSIFICATION_LEVEL = {
    "public": 0,
    "internal": 1,
    "confidential": 2,
    "restricted": 3,
}

ROLE_CLASSIFICATION_LIMIT = {
    "admin": "restricted",
    "maintainer": "confidential",
    "reviewer": "confidential",
    "auditor": "restricted",
    "viewer": "internal",
}


@dataclass
class RBACDecision:
    """Auditable RBAC decision for an enterprise resource request."""

    actor_id: str
    role: str
    action: str
    resource_type: str
    resource_id: str
    decision: str
    reason: str
    allowed_scope: str
    readiness_effect: str = "pass"
    sourceRefs: list[str] = field(default_factory=list)
    verdict_mutated: bool = False
    request_id: str = ""
    classification: str = "public"
    quarantine_status: str = "none"

    def to_dict(self) -> dict[str, Any]:
        return {
            "actor": self.actor_id,
            "actor_id": self.actor_id,
            "role": self.role,
            "action": self.action,
            "resource": {
                "type": self.resource_type,
                "id": self.resource_id,
                "classification": self.classification,
                "quarantine_status": self.quarantine_status,
            },
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "decision": self.decision,
            "reason": self.reason,
            "allowed_scope": self.allowed_scope,
            "readiness_effect": self.readiness_effect,
            "verdict_mutated": self.verdict_mutated,
            "request_id": self.request_id,
            "sourceRefs": self.sourceRefs,
        }

    @property
    def allowed(self) -> bool:
        return self.decision == "allowed"


def evaluate_rbac(
    actor: dict[str, Any],
    request: dict[str, Any],
    source_refs: list[str] | None = None,
) -> RBACDecision:
    """Evaluate RBAC for a local HATE resource request.

    Quarantined artifacts expose safe metadata only. Raw quarantined content is
    denied even for privileged roles because raw access would bypass quarantine.
    """

    source_refs = list(source_refs or request.get("sourceRefs") or actor.get("sourceRefs") or [])
    actor_id = str(actor.get("actor_id") or actor.get("id") or actor.get("actor") or "unknown")
    role = str(actor.get("role") or "viewer")
    scopes = set(str(scope) for scope in actor.get("scopes", []))
    action = str(request.get("action") or "read")
    resource_type = str(request.get("resource_type") or request.get("resource", {}).get("type") or "")
    resource_id = str(request.get("resource_id") or request.get("resource", {}).get("id") or "")
    classification = str(request.get("classification") or request.get("resource", {}).get("classification") or "public")
    quarantine_status = str(request.get("quarantine_status") or request.get("resource", {}).get("quarantine_status") or "none")
    access_level = str(request.get("access_level") or "safe_metadata")
    request_id = str(request.get("request_id") or "")

    if resource_type not in RESOURCE_TYPES:
        return _decision(
            actor_id,
            role,
            action,
            resource_type,
            resource_id,
            "denied",
            "unknown_resource_type",
            "none",
            source_refs,
            request_id,
            classification,
            quarantine_status,
        )

    if resource_type == "artifact" and quarantine_status == "quarantined":
        if access_level == "safe_metadata" and "safe_metadata" in scopes:
            return _decision(
                actor_id,
                role,
                action,
                resource_type,
                resource_id,
                "allowed",
                "quarantined_artifact_safe_metadata_only",
                "safe_metadata",
                source_refs,
                request_id,
                classification,
                quarantine_status,
            )
        return _decision(
            actor_id,
            role,
            action,
            resource_type,
            resource_id,
            "denied",
            "raw_quarantined_artifact_denied",
            "none",
            source_refs,
            request_id,
            classification,
            quarantine_status,
        )

    if resource_type == "export" and (
        access_level == "raw_artifact" or quarantine_status == "quarantined"
    ):
        return _decision(
            actor_id,
            role,
            action,
            resource_type,
            resource_id,
            "denied",
            "unsafe_export_scope_denied",
            "none",
            source_refs,
            request_id,
            classification,
            quarantine_status,
        )

    if action in ADMIN_ACTIONS and role != "admin":
        return _decision(
            actor_id,
            role,
            action,
            resource_type,
            resource_id,
            "denied",
            "admin_permission_required",
            "none",
            source_refs,
            request_id,
            classification,
            quarantine_status,
        )

    if not _role_allows(role, resource_type, action):
        return _decision(
            actor_id,
            role,
            action,
            resource_type,
            resource_id,
            "denied",
            "role_permission_denied",
            "none",
            source_refs,
            request_id,
            classification,
            quarantine_status,
        )

    if not _classification_allows(role, classification):
        return _decision(
            actor_id,
            role,
            action,
            resource_type,
            resource_id,
            "denied",
            "classification_scope_denied",
            "none",
            source_refs,
            request_id,
            classification,
            quarantine_status,
        )

    return _decision(
        actor_id,
        role,
        action,
        resource_type,
        resource_id,
        "allowed",
        "role_permission_allowed",
        _default_allowed_scope(resource_type, access_level, classification),
        source_refs,
        request_id,
        classification,
        quarantine_status,
    )


def _role_allows(role: str, resource_type: str, action: str) -> bool:
    permissions = ROLE_PERMISSIONS.get(role, {})
    return action in permissions.get("*", set()) or action in permissions.get(resource_type, set())


def _classification_allows(role: str, classification: str) -> bool:
    limit = ROLE_CLASSIFICATION_LIMIT.get(role, "public")
    return CLASSIFICATION_LEVEL.get(classification, 0) <= CLASSIFICATION_LEVEL.get(limit, 0)


def _default_allowed_scope(resource_type: str, access_level: str, classification: str) -> str:
    if resource_type == "artifact":
        return access_level if access_level else "safe_metadata"
    return classification


def _decision(
    actor_id: str,
    role: str,
    action: str,
    resource_type: str,
    resource_id: str,
    decision: str,
    reason: str,
    allowed_scope: str,
    source_refs: list[str],
    request_id: str,
    classification: str,
    quarantine_status: str,
) -> RBACDecision:
    return RBACDecision(
        actor_id=actor_id,
        role=role,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        decision=decision,
        reason=reason,
        allowed_scope=allowed_scope,
        readiness_effect="pass",
        sourceRefs=source_refs,
        verdict_mutated=False,
        request_id=request_id,
        classification=classification,
        quarantine_status=quarantine_status,
    )
