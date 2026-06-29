"""HATE-PG-005B Export filter for artifact safety.

Implements `filter_for_export(artifacts, surface)` to exclude quarantined artifacts
from external/support export while keeping safe metadata.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any


EXPORT_SURFACES = {
    "summary": {"allowed_classifications": ["public", "internal"]},
    "dashboard": {"allowed_classifications": ["public", "internal", "confidential"]},
    "support_bundle": {"allowed_classifications": ["public", "internal", "confidential"]},
    "qeg_export": {"allowed_classifications": ["public", "internal", "confidential"]},
    "diagnostic_bundle": {"allowed_classifications": ["public", "internal", "confidential"]},
    "external_export": {"allowed_classifications": ["public"]},
    "public": {"allowed_classifications": ["public"]},
}

QUARANTINE_STATUS_ORDER = {
    "none": 0,
    "released": 1,
    "quarantined": 2,
}


def _export_filter_id() -> str:
    return f"export-filter-{uuid.uuid4().hex[:12]}"


def _is_quarantined(artifact: dict[str, Any]) -> bool:
    """Check if artifact is quarantined."""
    quarantine_status = artifact.get("quarantine_status", "none")
    return quarantine_status == "quarantined"


def _is_redaction_failed(artifact: dict[str, Any]) -> bool:
    """Check if redaction failed."""
    redaction_status = artifact.get("redaction_status", "not_required")
    return redaction_status == "failed"


def _classification_allowed(classification: str, surface: str) -> bool:
    """Check if classification is allowed for export surface."""
    surface_config = EXPORT_SURFACES.get(surface, EXPORT_SURFACES["summary"])
    allowed = surface_config["allowed_classifications"]
    return classification in allowed


def _compute_export_hash(artifacts: list[dict]) -> str:
    """Compute hash of exported artifact IDs for verification."""
    ids = sorted([a.get("artifact_id", "unknown") for a in artifacts])
    combined = json.dumps(ids, sort_keys=True)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def filter_for_export(
    artifacts: list[dict[str, Any]],
    surface: str,
    *,
    profile: str = "default",
) -> dict[str, Any]:
    """Filter artifacts for export to specific surface.

    Args:
        artifacts: List of artifact manifests with classification, quarantine_status, redaction_status
        surface: Export surface (summary, dashboard, support_bundle, qeg_export, diagnostic_bundle, external_export, public)
        profile: Safety profile (default, strict, release, product)

    Returns:
        Export filter report with:
        - allowed_artifacts: Artifacts safe for this surface
        - excluded_artifacts: Artifacts blocked from this surface
        - hold_artifacts: Artifacts pending review/redaction
        - export_ready: boolean
        - readiness_effect: pass, soft_gap, hold, hard_dq
    """
    allowed: list[dict] = []
    excluded: list[dict] = []
    hold: list[dict] = []
    readiness_effects: list[str] = []

    for artifact in artifacts:
        artifact_id = artifact.get("artifact_id", "unknown")
        classification = artifact.get("classification", "internal")
        quarantine_status = artifact.get("quarantine_status", "none")
        redaction_status = artifact.get("redaction_status", "not_required")
        safe_for_summary = artifact.get("safe_for_summary", True)

        # Quarantined artifacts always excluded
        if _is_quarantined(artifact):
            excluded.append({
                "artifact_id": artifact_id,
                "reason": "quarantined",
                "classification": classification,
                "quarantine_status": quarantine_status,
            })
            readiness_effects.append("hard_dq")
            continue

        # Failed redaction = hold or hard_dq
        if _is_redaction_failed(artifact):
            if profile in {"release", "product"}:
                excluded.append({
                    "artifact_id": artifact_id,
                    "reason": "redaction_failed",
                    "classification": classification,
                    "redaction_status": redaction_status,
                })
                readiness_effects.append("hard_dq")
            else:
                hold.append({
                    "artifact_id": artifact_id,
                    "reason": "redaction_failed",
                    "classification": classification,
                    "redaction_status": redaction_status,
                })
                readiness_effects.append("hold")
            continue

        # Classification check
        if not _classification_allowed(classification, surface):
            excluded.append({
                "artifact_id": artifact_id,
                "reason": "classification_not_allowed",
                "classification": classification,
                "surface": surface,
            })
            # Restricted = hard_dq, confidential = hold (unless external_export)
            if classification == "restricted":
                readiness_effects.append("hard_dq")
            else:
                readiness_effects.append("hold")
            continue

        # Safe for summary check (for summary surface only)
        if surface == "summary" and not safe_for_summary:
            excluded.append({
                "artifact_id": artifact_id,
                "reason": "not_safe_for_summary",
                "classification": classification,
            })
            readiness_effects.append("soft_gap")
            continue

        # Artifact passes all checks
        allowed.append({
            "artifact_id": artifact_id,
            "classification": classification,
            "quarantine_status": quarantine_status,
            "redaction_status": redaction_status,
            "safe_for_summary": safe_for_summary,
        })

    # Determine final readiness
    if not artifacts:
        final_readiness = "pass"
        export_ready = True
    elif excluded:
        # Any exclusion = not ready for this surface
        export_ready = False
        effect_order = {"pass": 0, "soft_gap": 1, "hold": 2, "hard_dq": 3}
        if readiness_effects:
            final_readiness = sorted(readiness_effects, key=lambda e: effect_order.get(e, 0))[-1]
        else:
            final_readiness = "hard_dq"
    elif hold:
        # Hold artifacts mean export pending
        export_ready = False
        effect_order = {"pass": 0, "soft_gap": 1, "hold": 2, "hard_dq": 3}
        if readiness_effects:
            final_readiness = sorted(readiness_effects, key=lambda e: effect_order.get(e, 0))[-1]
        else:
            final_readiness = "hold"
    else:
        # All allowed
        export_ready = True
        final_readiness = "pass"

    report = {
        "schema_version": "HATE/v1",
        "record_type": "export-filter-report",
        "filter_id": _export_filter_id(),
        "surface": surface,
        "profile": profile,
        "export_ready": export_ready,
        "readiness_effect": final_readiness,
        "allowed_artifacts": allowed,
        "excluded_artifacts": excluded,
        "hold_artifacts": hold,
        "allowed_count": len(allowed),
        "excluded_count": len(excluded),
        "hold_count": len(hold),
        "export_hash": _compute_export_hash(allowed),
        "created_at": datetime.now(UTC).isoformat(),
        "summary": {
            "total_artifacts": len(artifacts),
            "allowed_count": len(allowed),
            "excluded_count": len(excluded),
            "hold_count": len(hold),
            "quarantined_excluded": sum(1 for e in excluded if e["reason"] == "quarantined"),
            "classification_excluded": sum(1 for e in excluded if e["reason"] == "classification_not_allowed"),
            "redaction_failed": sum(1 for e in excluded if e["reason"] == "redaction_failed"),
        },
    }

    return report