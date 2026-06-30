from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from .authz import is_allowed


SURFACE_ACTIONS = {
    "store": ("runs", "read"),
    "artifact": ("artifacts", "read_raw"),
    "cache": ("runs", "read"),
    "audit": ("audit-events", "read"),
    "export": ("artifacts", "export"),
    "support_bundle": ("artifacts", "read_summary"),
    "telemetry": ("product-readiness", "read"),
}


@dataclass
class TenantDecision:
    decision_id: str
    status: str
    readiness_effect: str
    finding_code: str = ""
    audit_events: list[dict[str, Any]] = field(default_factory=list)
    sanitized_payload: dict[str, Any] = field(default_factory=dict)

    def to_report(self, payload: dict[str, Any], *, source_version: str) -> dict[str, Any]:
        return {
            "schema_version": "HATE/v1",
            "record_type": "tenant-isolation-report",
            "source_version": source_version,
            "fixture_id": payload.get("fixture_id"),
            "gap_id": payload.get("gap_id", "HATE-GAP-002"),
            "status": self.status,
            "readiness_effect": self.readiness_effect,
            "finding_code": self.finding_code,
            "decision_id": self.decision_id,
            "audit_events": self.audit_events,
            "sanitized_payload": self.sanitized_payload,
            "sourceRefs": [payload.get("fixture_id", "tenant-isolation-fixture")],
        }


def evaluate_tenant_isolation_fixture(payload: dict[str, Any], *, source_version: str = "unknown") -> dict[str, Any]:
    data = payload.get("input", {})
    surface = str(data.get("surface") or "store")
    role = str(data.get("role") or "auditor")
    actor_tenant = str(data.get("actor_tenant") or "")
    resource_tenant = str(data.get("resource_tenant") or actor_tenant)
    action_resource, action = SURFACE_ACTIONS.get(surface, ("runs", "read"))
    decision = _evaluate_surface(
        surface=surface,
        role=role,
        actor_tenant=actor_tenant,
        resource_tenant=resource_tenant,
        action_resource=action_resource,
        action=action,
        data=data,
    )
    return decision.to_report(payload, source_version=source_version)


def _evaluate_surface(
    *,
    surface: str,
    role: str,
    actor_tenant: str,
    resource_tenant: str,
    action_resource: str,
    action: str,
    data: dict[str, Any],
) -> TenantDecision:
    audit_base = {
        "tenant_id": actor_tenant,
        "actor_id": str(data.get("actor_id") or "actor-local"),
        "role": role,
        "action": f"{surface}:{action}",
        "resource_ref": str(data.get("resource_ref") or f"{surface}:{resource_tenant}:resource"),
    }

    if surface == "audit" and data.get("global_auditor"):
        return _allow(audit_base, "global auditor explicitly scoped")

    if actor_tenant != resource_tenant:
        return _deny(audit_base, "tenant_cross_access_denied", "resource tenant does not match caller tenant")

    if not is_allowed(role, action_resource, action):
        return _deny(audit_base, "tenant_rbac_denied", f"{role} lacks {action_resource}:{action}")

    if surface == "cache":
        cache_key = str(data.get("cache_key") or "")
        if actor_tenant not in cache_key:
            return _deny(audit_base, "tenant_cache_key_missing_scope", "cache key must include tenant_id")

    if surface == "export":
        tenants = set(data.get("export_tenants", [actor_tenant]))
        if tenants != {actor_tenant}:
            return _deny(audit_base, "tenant_export_mixed_denied", "export cannot mix tenant bundles")

    if surface == "support_bundle":
        metadata_tenants = set(data.get("support_bundle_metadata_tenants", [actor_tenant]))
        if metadata_tenants - {actor_tenant}:
            return _deny(audit_base, "tenant_support_bundle_metadata_leak", "support bundle contains other tenant metadata")

    if surface == "telemetry":
        payload_data = data.get("telemetry_payload", {})
        forbidden = {"tenant_id", "organization_id", "workspace_id", "repo_url", "user_email"}
        if forbidden & set(payload_data):
            return _deny(audit_base, "tenant_telemetry_payload_denied", "telemetry includes tenant-identifying payload")
        return _allow(audit_base, "aggregate telemetry is tenant-safe", sanitized_payload=payload_data)

    return _allow(audit_base, "tenant and RBAC checks passed")


def _allow(audit_base: dict[str, Any], message: str, sanitized_payload: dict[str, Any] | None = None) -> TenantDecision:
    audit_event = {
        **audit_base,
        "decision": "allow",
        "message": message,
        "event_hash": _hash_event({**audit_base, "decision": "allow", "message": message}),
    }
    return TenantDecision(
        decision_id=audit_event["event_hash"],
        status="pass",
        readiness_effect="none",
        audit_events=[audit_event],
        sanitized_payload=sanitized_payload or {},
    )


def _deny(audit_base: dict[str, Any], code: str, message: str) -> TenantDecision:
    audit_event = {
        **audit_base,
        "decision": "deny",
        "message": message,
        "finding_code": code,
        "event_hash": _hash_event({**audit_base, "decision": "deny", "finding_code": code}),
    }
    return TenantDecision(
        decision_id=audit_event["event_hash"],
        status="hold",
        readiness_effect="hold",
        finding_code=code,
        audit_events=[audit_event],
    )


def _hash_event(event: dict[str, Any]) -> str:
    encoded = json.dumps(event, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"
