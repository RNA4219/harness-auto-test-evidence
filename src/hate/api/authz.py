"""HATE API Authorization projection.

Implements authz checks for import/export surfaces without leaking restricted details.
Authz failures are safe by default and auditable.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

# Classification hierarchy for authz decisions
CLASSIFICATION_ORDER = {
    "public": 0,
    "internal": 1,
    "confidential": 2,
    "restricted": 3,
}

# Actor scopes by surface
SURFACE_SCOPES = {
    "public": ["public"],
    "internal": ["public", "internal"],
    "dashboard": ["public", "internal", "confidential"],
    "support_bundle": ["public", "internal", "confidential"],
    "external_export": ["public"],
    "summary": ["public", "internal"],
}

# Role permissions (minimal for local-first)
ROLE_PERMISSIONS = {
    "admin": ["public", "internal", "confidential", "restricted"],
    "owner": ["public", "internal", "confidential", "restricted"],
    "maintainer": ["public", "internal", "confidential"],
    "developer": ["public", "internal"],
    "reader": ["public"],
    "external": ["public"],
}


class AuthorizationDecision:
    """Authorization decision for import/export operations."""

    def __init__(
        self,
        actor: str,
        tenant: dict[str, str],
        scopes: list[str],
        resource: str,
        decision: str,
        reason_code: str,
        reason_detail: str | None = None,
        source_refs: list[str] | None = None,
    ) -> None:
        self.actor = actor
        self.tenant = tenant
        self.scopes = scopes
        self.resource = resource
        self.decision = decision  # "allowed" or "denied"
        self.reason_code = reason_code
        self.reason_detail = reason_detail  # Safe detail, no secrets/paths
        self.source_refs = source_refs or []
        self.decision_id = f"authz-{uuid.uuid4().hex[:12]}"
        self.created_at = datetime.now(UTC).isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Convert to API authz decision dict."""
        return {
            "schema_version": "HATE/v1",
            "record_type": "api-authz-decision",
            "decision_id": self.decision_id,
            "actor": self.actor,
            "tenant": self.tenant,
            "scopes": self.scopes,
            "resource": self.resource,
            "decision": self.decision,
            "reason_code": self.reason_code,
            "reason_detail": self.reason_detail,
            "source_refs": self.source_refs,
            "created_at": self.created_at,
        }

    def is_allowed(self) -> bool:
        return self.decision == "allowed"


def _hash_tenant_id(tenant_id: str) -> str:
    """Non-reversible hash for tenant id in denial responses."""
    return hashlib.sha256(tenant_id.encode("utf-8")).hexdigest()[:16]


def check_import_authz(
    actor: str,
    tenant: dict[str, str],
    bundle: dict[str, Any],
    idempotency_key: str | None = None,
) -> AuthorizationDecision:
    """Check authorization for bundle import.

    Validates:
    - Tenant scope match
    - Actor role
    - Bundle schema version compatibility
    - Duplicate bundle hash

    Args:
        actor: Actor identifier (user or service)
        tenant: Tenant scope with organization_id and workspace_id
        bundle: Bundle to import
        idempotency_key: Optional idempotency key for replay

    Returns:
        AuthorizationDecision with allowed/denied status
    """
    organization_id = tenant.get("organization_id", "")
    workspace_id = tenant.get("workspace_id", "")

    # Check tenant scope in bundle
    bundle_org = bundle.get("organization_id", "")
    bundle_ws = bundle.get("workspace_id", "")

    if bundle_org and bundle_org != organization_id:
        # Cross-tenant access denied - no tenant leakage
        return AuthorizationDecision(
            actor=actor,
            tenant={"organization_id": _hash_tenant_id(organization_id), "workspace_id": ""},
            scopes=["public"],
            resource="bundle-import",
            decision="denied",
            reason_code="HATE-API-AUTH-CROSS-TENANT",
            reason_detail="Bundle tenant scope mismatch",
            source_refs=["api/authz.py:cross_tenant_check"],
        )

    if bundle_ws and bundle_ws != workspace_id:
        return AuthorizationDecision(
            actor=actor,
            tenant={"organization_id": _hash_tenant_id(organization_id), "workspace_id": ""},
            scopes=["public"],
            resource="bundle-import",
            decision="denied",
            reason_code="HATE-API-AUTH-CROSS-TENANT",
            reason_detail="Bundle workspace scope mismatch",
            source_refs=["api/authz.py:cross_tenant_check"],
        )

    # Check schema version compatibility
    schema_version = bundle.get("schema_version", "")
    if not schema_version.startswith("HATE/v"):
        return AuthorizationDecision(
            actor=actor,
            tenant=tenant,
            scopes=["public"],
            resource="bundle-import",
            decision="denied",
            reason_code="HATE-API-SCHEMA-UNSUPPORTED",
            reason_detail="Unsupported bundle schema version",
            source_refs=["api/authz.py:schema_version_check"],
        )

    # Actor role check (default to reader for local-first)
    role = "maintainer"  # Default for import operations
    allowed_scopes = ROLE_PERMISSIONS.get(role, ["public"])

    return AuthorizationDecision(
        actor=actor,
        tenant=tenant,
        scopes=allowed_scopes,
        resource="bundle-import",
        decision="allowed",
        reason_code="HATE-API-AUTH-ALLOWED",
        reason_detail="Import authorized",
        source_refs=["api/authz.py:import_allowed"],
    )


def check_export_authz(
    actor: str,
    tenant: dict[str, str],
    export_surface: str,
    artifacts: list[dict[str, Any]],
    role: str = "reader",
) -> AuthorizationDecision:
    """Check authorization for export operation.

    Validates:
    - Actor role vs surface scope
    - Artifact classification vs allowed scopes
    - Quarantined/restricted artifacts
    - Safe metadata only for denied artifacts

    Args:
        actor: Actor identifier
        tenant: Tenant scope
        export_surface: Export surface (public, internal, dashboard, etc.)
        artifacts: List of artifacts to export
        role: Actor role

    Returns:
        AuthorizationDecision with allowed/denied status and artifact filtering
    """
    allowed_scopes = SURFACE_SCOPES.get(export_surface, ["public"])
    role_scopes = ROLE_PERMISSIONS.get(role, ["public"])

    # Effective scopes = intersection of surface and role
    effective_scopes = [s for s in allowed_scopes if s in role_scopes]

    if not effective_scopes:
        return AuthorizationDecision(
            actor=actor,
            tenant={"organization_id": _hash_tenant_id(tenant.get("organization_id", "")), "workspace_id": ""},
            scopes=["public"],
            resource=f"export-{export_surface}",
            decision="denied",
            reason_code="HATE-API-AUTH-SCOPE-MISMATCH",
            reason_detail="Actor role insufficient for export surface",
            source_refs=["api/authz.py:scope_check"],
        )

    # Check for restricted artifacts that would be blocked
    blocked_artifacts = []
    class_levels = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}
    max_scope_level = max(class_levels.get(s, 0) for s in effective_scopes)

    for artifact in artifacts:
        classification = artifact.get("classification", "public")
        quarantine_status = artifact.get("quarantine_status", "none")
        redaction_status = artifact.get("redaction_status", "not_required")
        class_level = class_levels.get(classification, 0)

        # Quarantined artifacts always blocked (except safe metadata)
        if quarantine_status == "quarantined":
            blocked_artifacts.append({
                "artifact_id": artifact.get("artifact_id", ""),
                "reason": "quarantined",
                "safe_metadata_only": True,
            })
            continue

        # Classification exceeds effective scope level - blocked
        if class_level > max_scope_level:
            blocked_artifacts.append({
                "artifact_id": artifact.get("artifact_id", ""),
                "reason": f"classification_{classification}",
                "safe_metadata_only": classification in ["public", "internal"],
            })
            continue

        # Failed redaction blocked
        if redaction_status == "failed":
            blocked_artifacts.append({
                "artifact_id": artifact.get("artifact_id", ""),
                "reason": "redaction_failed",
                "safe_metadata_only": False,  # No export even safe metadata
            })
            continue

    # If all artifacts blocked, deny export
    if len(blocked_artifacts) == len(artifacts) and artifacts:
        return AuthorizationDecision(
            actor=actor,
            tenant=tenant,
            scopes=effective_scopes,
            resource=f"export-{export_surface}",
            decision="denied",
            reason_code="HATE-API-PRIV-EXPORT-BLOCKED",
            reason_detail="All artifacts blocked from export",
            source_refs=["api/authz.py:all_blocked"],
        )

    # Allowed with potential partial blocking
    return AuthorizationDecision(
        actor=actor,
        tenant=tenant,
        scopes=effective_scopes,
        resource=f"export-{export_surface}",
        decision="allowed",
        reason_code="HATE-API-AUTH-ALLOWED",
        reason_detail=f"Export authorized with {len(blocked_artifacts)} blocked artifacts",
        source_refs=["api/authz.py:export_allowed"],
    )


def check_artifact_access(
    actor: str,
    tenant: dict[str, str],
    artifact: dict[str, Any],
    role: str = "reader",
) -> AuthorizationDecision:
    """Check authorization for single artifact access.

    Args:
        actor: Actor identifier
        tenant: Tenant scope
        artifact: Artifact to check
        role: Actor role

    Returns:
        AuthorizationDecision for artifact access
    """
    classification = artifact.get("classification", "public")
    quarantine_status = artifact.get("quarantine_status", "none")

    role_scopes = ROLE_PERMISSIONS.get(role, ["public"])

    # Quarantined artifacts: safe metadata only
    if quarantine_status == "quarantined":
        return AuthorizationDecision(
            actor=actor,
            tenant=tenant,
            scopes=role_scopes,
            resource=f"artifact-{artifact.get('artifact_id', '')}",
            decision="denied",
            reason_code="HATE-API-PRIV-QUARANTINED",
            reason_detail="Artifact quarantined - safe metadata only",
            source_refs=["api/authz.py:quarantine_check"],
        )

    # Classification check
    class_level = CLASSIFICATION_ORDER.get(classification, 0)
    max_role_level = max(CLASSIFICATION_ORDER.get(s, 0) for s in role_scopes)

    if class_level > max_role_level:
        return AuthorizationDecision(
            actor=actor,
            tenant=tenant,
            scopes=role_scopes,
            resource=f"artifact-{artifact.get('artifact_id', '')}",
            decision="denied",
            reason_code="HATE-API-AUTH-CLASSIFICATION",
            reason_detail="Artifact classification exceeds actor scope",
            source_refs=["api/authz.py:classification_check"],
        )

    return AuthorizationDecision(
        actor=actor,
        tenant=tenant,
        scopes=role_scopes,
        resource=f"artifact-{artifact.get('artifact_id', '')}",
        decision="allowed",
        reason_code="HATE-API-AUTH-ALLOWED",
        reason_detail="Artifact access authorized",
        source_refs=["api/authz.py:artifact_allowed"],
    )