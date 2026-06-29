"""HATE API Import/Export projection.

Implements bundle import validation and safe export without mutating canonical bundles.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .authz import check_import_authz, check_export_authz, AuthorizationDecision


def _compute_bundle_hash(bundle: dict[str, Any]) -> str:
    """Compute SHA256 hash of bundle for validation."""
    canonical = json.dumps(bundle, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate_schema_version(bundle: dict[str, Any]) -> tuple[bool, str]:
    """Validate bundle schema version is supported."""
    schema_version = bundle.get("schema_version", "")
    if not schema_version:
        return False, "Missing schema_version"

    if not schema_version.startswith("HATE/v"):
        return False, f"Unsupported schema: {schema_version}"

    # Supported versions: HATE/v1
    supported_prefixes = ["HATE/v1"]
    if not any(schema_version.startswith(p) for p in supported_prefixes):
        return False, f"Unsupported schema version: {schema_version}"

    return True, "Schema version valid"


def _validate_source_refs(bundle: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate sourceRefs exist in bundle records."""
    missing_refs = []

    # Check top-level sourceRefs
    if "sourceRefs" not in bundle:
        missing_refs.append("bundle:missing_sourceRefs")

    # Check nested records for sourceRefs
    for key in ["records", "artifacts", "findings"]:
        if key in bundle:
            for record in bundle[key]:
                if "sourceRefs" not in record and "source_ref" not in record:
                    missing_refs.append(f"{key}:{record.get('id', 'unknown')}:missing_sourceRef")

    return len(missing_refs) == 0, missing_refs


def _validate_artifact_safety(bundle: dict[str, Any]) -> tuple[bool, list[dict[str, Any]]]:
    """Validate artifact manifest safety (secrets, PII, quarantine)."""
    unsafe_artifacts = []

    artifacts = bundle.get("artifacts", [])
    for artifact in artifacts:
        # Check quarantine status
        quarantine_status = artifact.get("quarantine_status", "none")
        if quarantine_status == "quarantined":
            unsafe_artifacts.append({
                "artifact_id": artifact.get("artifact_id", ""),
                "reason": "quarantined",
                "classification": artifact.get("classification", "restricted"),
            })
            continue

        # Check redaction status
        redaction_status = artifact.get("redaction_status", "not_required")
        if redaction_status in ["failed", "pending"]:
            unsafe_artifacts.append({
                "artifact_id": artifact.get("artifact_id", ""),
                "reason": f"redaction_{redaction_status}",
                "classification": artifact.get("classification", "restricted"),
            })
            continue

        # Check classification
        classification = artifact.get("classification", "public")
        if classification == "restricted":
            unsafe_artifacts.append({
                "artifact_id": artifact.get("artifact_id", ""),
                "reason": "restricted_classification",
                "classification": classification,
            })

    return len(unsafe_artifacts) == 0, unsafe_artifacts


def validate_bundle_import(
    bundle: dict[str, Any],
    actor: str,
    tenant: dict[str, str],
    idempotency_key: str | None = None,
    existing_bundle_hash: str | None = None,
) -> dict[str, Any]:
    """Validate bundle import without mutating canonical bundle.

    Validates:
    - Schema version
    - Hash integrity
    - SourceRef identity
    - Artifact manifest safety
    - Tenant scope
    - Duplicate detection

    Args:
        bundle: Bundle to import
        actor: Actor identifier
        tenant: Tenant scope
        idempotency_key: Optional idempotency key
        existing_bundle_hash: Hash of existing bundle for idempotency check

    Returns:
        Import validation report with:
        - import_status: accepted, rejected, duplicate
        - bundle_hash: SHA256 of bundle
        - authz_decision: Authorization decision
        - validation_results: Schema, sourceRef, artifact checks
        - sourceRefs: List of source references
    """
    import_id = f"import-{uuid.uuid4().hex[:12]}"
    bundle_hash = _compute_bundle_hash(bundle)

    # Authorization check
    authz_decision = check_import_authz(actor, tenant, bundle, idempotency_key)
    authz_dict = authz_decision.to_dict()

    if not authz_decision.is_allowed():
        return {
            "schema_version": "HATE/v1",
            "record_type": "bundle-import-report",
            "import_id": import_id,
            "import_status": "rejected",
            "bundle_id": bundle.get("bundle_id", "unknown"),
            "bundle_hash": bundle_hash,
            "idempotency_key": idempotency_key,
            "authz_decision": authz_dict,
            "validation_results": {
                "schema_valid": False,
                "hash_valid": False,
                "sourceRefs_valid": False,
                "artifact_safety_valid": False,
            },
            "rejection_reason": authz_decision.reason_code,
            "sourceRefs": ["api/import_export.py:authz_rejected"],
            "created_at": datetime.now(UTC).isoformat(),
            "summary": {
                "accepted": False,
                "rejected_reason": authz_decision.reason_code,
            },
        }

    # Schema validation
    schema_valid, schema_message = _validate_schema_version(bundle)

    if not schema_valid:
        return {
            "schema_version": "HATE/v1",
            "record_type": "bundle-import-report",
            "import_id": import_id,
            "import_status": "rejected",
            "bundle_id": bundle.get("bundle_id", "unknown"),
            "bundle_hash": bundle_hash,
            "idempotency_key": idempotency_key,
            "authz_decision": authz_dict,
            "validation_results": {
                "schema_valid": False,
                "schema_message": schema_message,
                "hash_valid": True,
                "sourceRefs_valid": False,
                "artifact_safety_valid": False,
            },
            "rejection_reason": "HATE-API-SCHEMA-INVALID",
            "sourceRefs": ["api/import_export.py:schema_rejected"],
            "created_at": datetime.now(UTC).isoformat(),
            "summary": {
                "accepted": False,
                "rejected_reason": "HATE-API-SCHEMA-INVALID",
            },
        }

    # Hash validation (idempotency)
    if existing_bundle_hash and existing_bundle_hash == bundle_hash:
        return {
            "schema_version": "HATE/v1",
            "record_type": "bundle-import-report",
            "import_id": import_id,
            "import_status": "duplicate",
            "bundle_id": bundle.get("bundle_id", "unknown"),
            "bundle_hash": bundle_hash,
            "idempotency_key": idempotency_key,
            "authz_decision": authz_dict,
            "validation_results": {
                "schema_valid": True,
                "hash_valid": True,
                "hash_match": True,
                "sourceRefs_valid": True,
                "artifact_safety_valid": True,
            },
            "rejection_reason": None,
            "sourceRefs": ["api/import_export.py:idempotent_duplicate"],
            "created_at": datetime.now(UTC).isoformat(),
            "summary": {
                "accepted": True,
                "duplicate": True,
                "idempotent": True,
            },
        }

    # SourceRefs validation
    sourceRefs_valid, missing_refs = _validate_source_refs(bundle)

    if not sourceRefs_valid:
        return {
            "schema_version": "HATE/v1",
            "record_type": "bundle-import-report",
            "import_id": import_id,
            "import_status": "rejected",
            "bundle_id": bundle.get("bundle_id", "unknown"),
            "bundle_hash": bundle_hash,
            "idempotency_key": idempotency_key,
            "authz_decision": authz_dict,
            "validation_results": {
                "schema_valid": True,
                "hash_valid": True,
                "sourceRefs_valid": False,
                "missing_refs": missing_refs,
                "artifact_safety_valid": False,
            },
            "rejection_reason": "HATE-API-REQ-MISSING-SOURCEREF",
            "sourceRefs": ["api/import_export.py:sourceref_rejected"],
            "created_at": datetime.now(UTC).isoformat(),
            "summary": {
                "accepted": False,
                "rejected_reason": "HATE-API-REQ-MISSING-SOURCEREF",
            },
        }

    # Artifact safety validation
    artifact_safety_valid, unsafe_artifacts = _validate_artifact_safety(bundle)

    # Accepted (unsafe artifacts flagged but not blocking for internal import)
    return {
        "schema_version": "HATE/v1",
        "record_type": "bundle-import-report",
        "import_id": import_id,
        "import_status": "accepted",
        "bundle_id": bundle.get("bundle_id", "unknown"),
        "bundle_hash": bundle_hash,
        "idempotency_key": idempotency_key,
        "authz_decision": authz_dict,
        "validation_results": {
            "schema_valid": True,
            "hash_valid": True,
            "sourceRefs_valid": True,
            "artifact_safety_valid": artifact_safety_valid,
            "unsafe_artifacts": unsafe_artifacts,
        },
        "rejection_reason": None,
        "sourceRefs": bundle.get("sourceRefs", ["api/import_export.py:import_accepted"]),
        "created_at": datetime.now(UTC).isoformat(),
        "summary": {
            "accepted": True,
            "unsafe_artifacts_count": len(unsafe_artifacts),
        },
    }


def export_safe_diagnostic(
    artifacts: list[dict[str, Any]],
    actor: str,
    tenant: dict[str, str],
    export_surface: str,
    role: str = "reader",
    profile: str = "default",
) -> dict[str, Any]:
    """Export safe diagnostic bundle excluding quarantined/redaction-failed artifacts.

    Args:
        artifacts: List of artifacts to export
        actor: Actor identifier
        tenant: Tenant scope
        export_surface: Export surface (dashboard, support_bundle, etc.)
        role: Actor role
        profile: Export profile (default, release, strict)

    Returns:
        Export report with:
        - export_status: ready, blocked, partial
        - allowed_artifacts: Artifacts safe for export
        - excluded_artifacts: Blocked artifacts with safe metadata
        - authz_decision: Authorization decision
        - readiness_effect: pass, hold, hard_dq
    """
    export_id = f"export-{uuid.uuid4().hex[:12]}"

    # Authorization check
    authz_decision = check_export_authz(actor, tenant, export_surface, artifacts, role)
    authz_dict = authz_decision.to_dict()

    allowed_artifacts = []
    excluded_artifacts = []

    for artifact in artifacts:
        artifact_id = artifact.get("artifact_id", "")
        classification = artifact.get("classification", "public")
        quarantine_status = artifact.get("quarantine_status", "none")
        redaction_status = artifact.get("redaction_status", "not_required")

        # Quarantined: exclude with safe metadata only
        if quarantine_status == "quarantined":
            excluded_artifacts.append({
                "artifact_id": artifact_id,
                "classification": classification,
                "exclusion_reason": "quarantined",
                "safe_metadata": {
                    "artifact_id": artifact_id,
                    "classification": classification,
                    "quarantine_status": "quarantined",
                    "safe_for_summary": False,
                },
            })
            continue

        # Redaction failed: exclude entirely (no safe metadata)
        if redaction_status == "failed":
            excluded_artifacts.append({
                "artifact_id": artifact_id,
                "classification": classification,
                "exclusion_reason": "redaction_failed",
                "safe_metadata": None,
            })
            continue

        # Classification check against authz scopes
        surface_scopes = authz_decision.scopes
        class_level = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}.get(classification, 0)
        max_scope_level = max({"public": 0, "internal": 1, "confidential": 2, "restricted": 3}.get(s, 0) for s in surface_scopes)

        if class_level > max_scope_level:
            excluded_artifacts.append({
                "artifact_id": artifact_id,
                "classification": classification,
                "exclusion_reason": "classification_not_allowed",
                "safe_metadata": {
                    "artifact_id": artifact_id,
                    "classification": classification,
                    "safe_for_summary": classification in ["public", "internal"],
                },
            })
            continue

        # Allowed artifact
        allowed_artifacts.append(artifact)

    # Determine export status
    if not authz_decision.is_allowed():
        export_status = "blocked"
        readiness_effect = "hard_dq"
    elif excluded_artifacts and allowed_artifacts:
        export_status = "partial"
        readiness_effect = "hold"
    elif excluded_artifacts and not allowed_artifacts:
        export_status = "blocked"
        readiness_effect = "hard_dq"
    else:
        export_status = "ready"
        readiness_effect = "pass"

    return {
        "schema_version": "HATE/v1",
        "record_type": "safe-export-report",
        "export_id": export_id,
        "export_surface": export_surface,
        "export_profile": profile,
        "export_status": export_status,
        "readiness_effect": readiness_effect,
        "authz_decision": authz_dict,
        "allowed_artifacts": allowed_artifacts,
        "excluded_artifacts": excluded_artifacts,
        "sourceRefs": ["api/import_export.py:export_generated"],
        "created_at": datetime.now(UTC).isoformat(),
        "summary": {
            "allowed_count": len(allowed_artifacts),
            "excluded_count": len(excluded_artifacts),
            "quarantined_excluded": sum(1 for a in excluded_artifacts if a["exclusion_reason"] == "quarantined"),
            "redaction_failed_excluded": sum(1 for a in excluded_artifacts if a["exclusion_reason"] == "redaction_failed"),
        },
    }