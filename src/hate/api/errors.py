"""HATE API Error Taxonomy.

Implements structured error responses for API read model.
All errors are safe-by-default and auditable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
import uuid


# Error code prefixes (per API_REQUIREMENTS.md Section 7)
ERROR_PREFIX_AUTH = "HATE-API-AUTH"
ERROR_PREFIX_REQ = "HATE-API-REQ"
ERROR_PREFIX_SCHEMA = "HATE-API-SCHEMA"
ERROR_PREFIX_STORE = "HATE-API-STORE"
ERROR_PREFIX_EXPORT = "HATE-API-EXPORT"
ERROR_PREFIX_PRIV = "HATE-API-PRIV"


@dataclass
class APIError:
    """Structured API error."""
    code: str  # Non-default first
    message: str  # Non-default first
    remediation: str = ""
    source_refs: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to API error dict."""
        return {
            "code": self.code,
            "message": self.message,
            "remediation": self.remediation,
            "source_refs": self.source_refs,
            "details": self.details,
        }


# Authentication/Authorization errors
def auth_unauthenticated() -> APIError:
    """Missing or invalid authentication."""
    return APIError(
        code=f"{ERROR_PREFIX_AUTH}-UNAUTHENTICATED",
        message="Authentication required",
        remediation="Provide valid service token or user token",
        source_refs=["api/errors.py:auth_unauthenticated"],
    )


def auth_unauthorized(resource: str) -> APIError:
    """Insufficient permissions."""
    return APIError(
        code=f"{ERROR_PREFIX_AUTH}-UNAUTHORIZED",
        message=f"Not authorized to access {resource}",
        remediation="Check role permissions or request access from admin",
        source_refs=["api/errors.py:auth_unauthorized"],
        details={"resource": resource},
    )


def auth_cross_tenant() -> APIError:
    """Cross-tenant access attempt."""
    return APIError(
        code=f"{ERROR_PREFIX_AUTH}-CROSS-TENANT",
        message="Cross-tenant access denied",
        remediation="Verify organization_id and workspace_id match your tenant scope",
        source_refs=["api/errors.py:auth_cross_tenant"],
    )


# Request/Filter/Pagination errors
def req_invalid_filter(filter_name: str, reason: str) -> APIError:
    """Invalid filter parameter."""
    return APIError(
        code=f"{ERROR_PREFIX_REQ}-INVALID-FILTER",
        message=f"Invalid filter '{filter_name}': {reason}",
        remediation="Check filter syntax and allowed values",
        source_refs=["api/errors.py:req_invalid_filter"],
        details={"filter": filter_name, "reason": reason},
    )


def req_invalid_pagination(reason: str) -> APIError:
    """Invalid pagination parameter."""
    return APIError(
        code=f"{ERROR_PREFIX_REQ}-INVALID-PAGINATION",
        message=f"Invalid pagination: {reason}",
        remediation="Use valid limit (1-1000) and cursor format",
        source_refs=["api/errors.py:req_invalid_pagination"],
        details={"reason": reason},
    )


def req_missing_required(param_name: str) -> APIError:
    """Missing required parameter."""
    return APIError(
        code=f"{ERROR_PREFIX_REQ}-MISSING-REQUIRED",
        message=f"Missing required parameter: {param_name}",
        remediation=f"Provide {param_name} in request",
        source_refs=["api/errors.py:req_missing_required"],
        details={"parameter": param_name},
    )


def req_invalid_sort(sort_field: str) -> APIError:
    """Invalid sort field."""
    return APIError(
        code=f"{ERROR_PREFIX_REQ}-INVALID-SORT",
        message=f"Invalid sort field: {sort_field}",
        remediation="Use allowed sort fields for this resource",
        source_refs=["api/errors.py:req_invalid_sort"],
        details={"field": sort_field},
    )


# Schema errors
def schema_unsupported(version: str) -> APIError:
    """Unsupported schema version."""
    return APIError(
        code=f"{ERROR_PREFIX_SCHEMA}-UNSUPPORTED",
        message=f"Unsupported schema version: {version}",
        remediation="Use supported schema version (HATE/v1)",
        source_refs=["api/errors.py:schema_unsupported"],
        details={"version": version},
    )


def schema_incompatible(profile: str) -> APIError:
    """Schema/profile incompatible."""
    return APIError(
        code=f"{ERROR_PREFIX_SCHEMA}-INCOMPATIBLE",
        message=f"Schema incompatible with profile: {profile}",
        remediation="Check profile schema requirements or migrate bundle",
        source_refs=["api/errors.py:schema_incompatible"],
        details={"profile": profile},
    )


# Store/Staleness errors
def store_not_found(resource_type: str, resource_id: str) -> APIError:
    """Resource not found in store."""
    return APIError(
        code=f"{ERROR_PREFIX_STORE}-NOT-FOUND",
        message=f"{resource_type} not found: {resource_id}",
        remediation="Check resource ID or wait for import",
        source_refs=["api/errors.py:store_not_found"],
        details={"resource_type": resource_type, "resource_id": resource_id},
    )


def store_stale(reason: str) -> APIError:
    """Read model is stale."""
    return APIError(
        code=f"{ERROR_PREFIX_STORE}-STALE",
        message=f"Read model stale: {reason}",
        remediation="Wait for rebuild or check bundle import status",
        source_refs=["api/errors.py:store_stale"],
        details={"reason": reason},
    )


def store_rebuilding() -> APIError:
    """Read model is rebuilding."""
    return APIError(
        code=f"{ERROR_PREFIX_STORE}-REBUILDING",
        message="Read model rebuilding from canonical bundle",
        remediation="Wait for rebuild completion or use cached data",
        source_refs=["api/errors.py:store_rebuilding"],
    )


def store_corruption(bundle_id: str) -> APIError:
    """Store corruption detected."""
    return APIError(
        code=f"{ERROR_PREFIX_STORE}-CORRUPTION",
        message=f"Store corruption detected in bundle: {bundle_id}",
        remediation="Run doctor diagnosis or re-import canonical bundle",
        source_refs=["api/errors.py:store_corruption"],
        details={"bundle_id": bundle_id},
    )


# Export errors (non-gating)
def export_failed(provider: str, reason: str) -> APIError:
    """External export failed (non-gating)."""
    return APIError(
        code=f"{ERROR_PREFIX_EXPORT}-FAILED",
        message=f"Export to {provider} failed: {reason}",
        remediation="Check provider configuration or retry later",
        source_refs=["api/errors.py:export_failed"],
        details={"provider": provider, "reason": reason},
    )


def export_blocked(reason: str) -> APIError:
    """Export blocked by policy."""
    return APIError(
        code=f"{ERROR_PREFIX_EXPORT}-BLOCKED",
        message=f"Export blocked: {reason}",
        remediation="Review export policy or contact admin",
        source_refs=["api/errors.py:export_blocked"],
        details={"reason": reason},
    )


# Privacy/Quarantine errors
def priv_quarantined(artifact_id: str) -> APIError:
    """Artifact quarantined."""
    return APIError(
        code=f"{ERROR_PREFIX_PRIV}-QUARANTINED",
        message=f"Artifact quarantined: {artifact_id}",
        remediation="Safe metadata only available; content access requires admin approval",
        source_refs=["api/errors.py:priv_quarantined"],
        details={"artifact_id": artifact_id},
    )


def priv_redaction_failed(artifact_id: str) -> APIError:
    """Redaction failed."""
    return APIError(
        code=f"{ERROR_PREFIX_PRIV}-REDACTION-FAILED",
        message=f"Redaction failed for artifact: {artifact_id}",
        remediation="Artifact unavailable; contact security team",
        source_refs=["api/errors.py:priv_redaction_failed"],
        details={"artifact_id": artifact_id},
    )


def priv_restricted(artifact_id: str) -> APIError:
    """Artifact classification restricted."""
    return APIError(
        code=f"{ERROR_PREFIX_PRIV}-RESTRICTED",
        message=f"Artifact classification restricted: {artifact_id}",
        remediation="Request elevated role or safe summary only",
        source_refs=["api/errors.py:priv_restricted"],
        details={"artifact_id": artifact_id},
    )


def priv_path_leak_prevented() -> APIError:
    """Path leak prevented."""
    return APIError(
        code=f"{ERROR_PREFIX_PRIV}-PATH-LEAK-PREVENTED",
        message="Restricted path access prevented",
        remediation="Unauthorized paths not exposed",
        source_refs=["api/errors.py:priv_path_leak_prevented"],
    )


def error_list_to_dict(errors: list[APIError]) -> list[dict[str, Any]]:
    """Convert list of APIError to list of dicts."""
    return [e.to_dict() for e in errors]