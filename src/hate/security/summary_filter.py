"""HATE-PG-005B Summary filter for display safety.

Implements `filter_for_summary(artifacts, surface)` for display-only safety
without changing readiness verdicts. Controls visibility per surface.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any


# Summary visibility rules per surface
SUMMARY_SURFACE_CONFIG = {
    "dashboard": {
        "show_redacted_content": True,
        "show_redaction_markers": True,
        "show_classification": True,
        "show_quarantine_status": True,
        "show_redaction_log": False,
        "allowed_classifications": ["public", "internal", "confidential"],
    },
    "support": {
        "show_redacted_content": True,
        "show_redaction_markers": True,
        "show_classification": True,
        "show_quarantine_status": True,
        "show_redaction_log": True,  # Support needs full context
        "allowed_classifications": ["public", "internal", "confidential"],
    },
    "public": {
        "show_redacted_content": False,  # Never show content to public
        "show_redaction_markers": False,
        "show_classification": False,  # Hide classification
        "show_quarantine_status": True,  # Show quarantine status only
        "show_redaction_log": False,
        "allowed_classifications": ["public"],
    },
    "internal": {
        "show_redacted_content": True,
        "show_redaction_markers": True,
        "show_classification": True,
        "show_quarantine_status": True,
        "show_redaction_log": True,
        "allowed_classifications": ["public", "internal", "confidential"],
    },
    "qeg": {
        "show_redacted_content": True,
        "show_redaction_markers": True,
        "show_classification": True,
        "show_quarantine_status": True,
        "show_redaction_log": True,
        "allowed_classifications": ["public", "internal", "confidential"],
    },
}


def _summary_filter_id() -> str:
    return f"summary-filter-{uuid.uuid4().hex[:12]}"


def _is_quarantined(artifact: dict[str, Any]) -> bool:
    """Check if artifact is quarantined."""
    return artifact.get("quarantine_status", "none") == "quarantined"


def _is_safe_for_summary(artifact: dict[str, Any]) -> bool:
    """Check if artifact is marked safe for summary display."""
    return artifact.get("safe_for_summary", True)


def _compute_summary_hash(artifacts: list[dict]) -> str:
    """Compute hash of summary-visible artifact IDs."""
    ids = sorted([a.get("artifact_id", "unknown") for a in artifacts])
    combined = json.dumps(ids, sort_keys=True)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def filter_for_summary(
    artifacts: list[dict[str, Any]],
    surface: str,
) -> dict[str, Any]:
    """Filter artifacts for summary display on specific surface.

    CRITICAL: This filter NEVER changes readiness verdicts.
    It only controls what is visible for display.

    Args:
        artifacts: List of artifact manifests with classification, quarantine_status, safe_for_summary
        surface: Display surface (dashboard, support, public, internal, qeg)

    Returns:
        Summary filter report with:
        - visible_artifacts: Artifacts safe to display
        - hidden_artifacts: Artifacts blocked from display
        - display_config: Visibility settings for this surface
        - summary_hash: Hash of visible artifact IDs
        - readiness_effect: Preserved from input (NEVER changed)
    """
    config = SUMMARY_SURFACE_CONFIG.get(surface, SUMMARY_SURFACE_CONFIG["internal"])
    visible: list[dict] = []
    hidden: list[dict] = []

    for artifact in artifacts:
        artifact_id = artifact.get("artifact_id", "unknown")
        classification = artifact.get("classification", "internal")
        quarantine_status = artifact.get("quarantine_status", "none")
        safe_for_summary = artifact.get("safe_for_summary", True)
        readiness_effect = artifact.get("readiness_effect", "pass")

        # Quarantined artifacts hidden from all surfaces
        if _is_quarantined(artifact):
            hidden.append({
                "artifact_id": artifact_id,
                "reason": "quarantined",
                "original_readiness_effect": readiness_effect,
            })
            continue

        # Classification visibility check
        if classification not in config["allowed_classifications"]:
            hidden.append({
                "artifact_id": artifact_id,
                "reason": "classification_not_visible",
                "classification": classification,
                "surface": surface,
                "original_readiness_effect": readiness_effect,
            })
            continue

        # safe_for_summary check
        if not safe_for_summary and surface != "support":
            # Support can see unsafe artifacts for debugging
            hidden.append({
                "artifact_id": artifact_id,
                "reason": "not_safe_for_summary",
                "original_readiness_effect": readiness_effect,
            })
            continue

        # Build visible artifact summary
        visible_entry = {
            "artifact_id": artifact_id,
            "classification": classification,
            "quarantine_status": quarantine_status,
            "safe_for_summary": safe_for_summary,
            "original_readiness_effect": readiness_effect,
        }

        # Add display fields based on config
        if config["show_classification"]:
            visible_entry["classification_display"] = classification
        if config["show_quarantine_status"]:
            visible_entry["quarantine_status_display"] = quarantine_status
        if config["show_redaction_markers"]:
            redaction_count = artifact.get("redaction_log", [])
            if isinstance(redaction_count, list):
                visible_entry["redaction_count"] = len(redaction_count)
            else:
                visible_entry["redaction_count"] = 0

        visible.append(visible_entry)

    # Compute readiness_effect from input artifacts (NEVER change)
    input_readiness_effects = [
        a.get("readiness_effect", "pass")
        for a in artifacts
        if a.get("readiness_effect")
    ]

    if input_readiness_effects:
        # Preserve the worst readiness from input
        effect_order = {"pass": 0, "soft_gap": 1, "hold": 2, "hard_dq": 3}
        preserved_readiness = sorted(input_readiness_effects, key=lambda e: effect_order.get(e, 0))[-1]
    else:
        preserved_readiness = "pass"

    report = {
        "schema_version": "HATE/v1",
        "record_type": "summary-filter-report",
        "filter_id": _summary_filter_id(),
        "surface": surface,
        "display_config": config,
        "visible_artifacts": visible,
        "hidden_artifacts": hidden,
        "visible_count": len(visible),
        "hidden_count": len(hidden),
        "summary_hash": _compute_summary_hash(visible),
        "readiness_effect": preserved_readiness,  # PRESERVED from input
        "created_at": datetime.now(UTC).isoformat(),
        "summary": {
            "total_artifacts": len(artifacts),
            "visible_count": len(visible),
            "hidden_count": len(hidden),
            "quarantined_hidden": sum(1 for h in hidden if h["reason"] == "quarantined"),
            "classification_hidden": sum(1 for h in hidden if h["reason"] == "classification_not_visible"),
            "unsafe_hidden": sum(1 for h in hidden if h["reason"] == "not_safe_for_summary"),
        },
    }

    return report


def get_summary_display_config(surface: str) -> dict[str, Any]:
    """Get display configuration for a summary surface.

    Args:
        surface: Display surface name

    Returns:
        Display configuration dict
    """
    return SUMMARY_SURFACE_CONFIG.get(surface, SUMMARY_SURFACE_CONFIG["internal"])