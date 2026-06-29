"""Legal hold evaluation for enterprise control projections."""

from __future__ import annotations

from datetime import datetime
from typing import Any


REQUIRED_LEGAL_HOLD_FIELDS = {"status", "reason", "held_since", "authorized_by"}
MUTATING_OPERATIONS = {"purge", "delete", "export_raw", "mutate_export", "release_hold"}


def evaluate_legal_hold(
    resource: dict[str, Any],
    operation: str = "read",
    profile: str = "default",
) -> dict[str, Any]:
    """Evaluate legal hold metadata without mutating the resource."""

    legal_hold = resource.get("legal_hold") or {}
    source_refs = list(resource.get("sourceRefs") or [])
    resource_id = str(resource.get("resource_id") or resource.get("bundle_id") or resource.get("artifact_id") or "")

    if not legal_hold:
        effect = "hard_dq" if profile in {"release", "regulated"} else "hold"
        return _result(resource_id, operation, "missing_legal_hold", effect, source_refs)

    missing = sorted(field for field in REQUIRED_LEGAL_HOLD_FIELDS if not legal_hold.get(field))
    if missing:
        effect = "hard_dq" if profile in {"release", "regulated"} else "hold"
        return _result(resource_id, operation, "legal_hold_incomplete", effect, source_refs, {"missing_fields": missing})

    status = str(legal_hold.get("status"))
    if status == "active" and legal_hold_blocks_operation(legal_hold, operation):
        return _result(resource_id, operation, "legal_hold_blocks_mutation", "hard_dq", source_refs)

    if status == "active":
        return _result(resource_id, operation, "legal_hold_active", "pass", source_refs)

    if status not in {"inactive", "released", "none"}:
        return _result(resource_id, operation, "legal_hold_unknown_status", "hold", source_refs)

    return _result(resource_id, operation, "legal_hold_clear", "pass", source_refs)


def legal_hold_blocks_operation(legal_hold: dict[str, Any], operation: str) -> bool:
    """Return true when active legal hold blocks a mutating operation."""

    return legal_hold.get("status") == "active" and operation in MUTATING_OPERATIONS


def legal_hold_preserved(before: dict[str, Any], after: dict[str, Any]) -> bool:
    """Check migration/replay preservation for legal hold metadata."""

    return (before.get("legal_hold") or {}) == (after.get("legal_hold") or {})


def _result(
    resource_id: str,
    operation: str,
    code: str,
    readiness_effect: str,
    source_refs: list[str],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    finding = {
        "code": code,
        "severity": _severity(readiness_effect),
        "message": code.replace("_", " "),
        "sourceRef": source_refs[0] if source_refs else "",
    }
    if extra:
        finding.update(extra)
    return {
        "resource_id": resource_id,
        "operation": operation,
        "status": code,
        "readiness_effect": readiness_effect,
        "finding": finding if readiness_effect != "pass" else None,
        "sourceRefs": source_refs,
    }


def _severity(effect: str) -> str:
    if effect == "hard_dq":
        return "critical"
    if effect == "hold":
        return "high"
    if effect == "soft_gap":
        return "medium"
    return "info"
