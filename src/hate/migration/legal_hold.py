"""Legal hold migration preservation checks."""

from __future__ import annotations

from typing import Any

from hate.enterprise.legal_hold import legal_hold_blocks_operation
from hate.migration.compatibility import evaluate_migration_compatibility


MUTATION_OPERATIONS = {"export", "purge", "delete", "replay", "retention_transition", "migration"}


def evaluate_legal_hold_migration(
    scenario: dict[str, Any],
    *,
    profile: str = "release",
) -> dict[str, Any]:
    """Evaluate legal hold preservation across migration/export/replay transitions."""

    before = dict(scenario.get("before") or {})
    after = dict(scenario.get("after") or {})
    operation = str(scenario.get("operation") or "migration")
    source_refs = list(before.get("sourceRefs") or scenario.get("sourceRefs") or [])
    source_bundle = _bundle_from_state(before)
    migrated_bundle = _bundle_from_state(after)
    compatibility = evaluate_migration_compatibility(
        source_bundle,
        migrated_bundle,
        target_version=str(scenario.get("target_version") or "HATE/v1"),
        profile=profile,
    ).to_dict()

    findings = list(compatibility.get("findings", []))
    before_hold = before.get("legal_hold") or {}
    after_hold = after.get("legal_hold") or {}
    active_before = before_hold.get("status") == "active"

    if operation not in MUTATION_OPERATIONS:
        findings.append(_finding("unknown_legal_hold_migration_operation", "hold", "Unknown legal hold migration operation.", source_refs))
    if active_before and not after_hold:
        findings.append(_finding("legal_hold_lost", "hard_dq", "Legal hold metadata was dropped.", source_refs))
    if active_before and before_hold != after_hold:
        findings.append(_finding("legal_hold_changed", "hard_dq", "Legal hold metadata changed during transition.", source_refs))
    if active_before and _operation_attempts_hold_blocked_mutation(operation, after, before_hold):
        findings.append(_finding("legal_hold_blocks_mutation", "hard_dq", f"Legal hold blocks {operation}.", source_refs))
    if operation == "replay" and active_before and not after.get("replay_report", {}).get("legal_hold_preserved", True):
        findings.append(_finding("replay_drops_legal_hold", "hard_dq", "Replay report indicates legal hold was not preserved.", source_refs))
    if operation == "retention_transition" and active_before and after.get("retention_action") in {"purge", "delete"}:
        findings.append(_finding("retention_transition_bypasses_hold", "hard_dq", "Retention transition attempted purge/delete during legal hold.", source_refs))

    effect = _max_effect(finding["readiness_effect"] for finding in findings)
    return {
        "operation": operation,
        "resource_id": str(before.get("resource_id") or before.get("bundle_id") or ""),
        "legal_hold_preserved": before_hold == after_hold,
        "mutation_blocked": any(f["code"] == "legal_hold_blocks_mutation" for f in findings),
        "readiness_effect": effect,
        "decision": "pass" if effect == "pass" else ("hold" if effect == "hold" else "blocked"),
        "compatibility_decision": compatibility,
        "findings": findings,
        "sourceRefs": source_refs,
    }


def build_legal_hold_migration_report(
    scenarios: list[dict[str, Any]],
    *,
    profile: str = "release",
) -> dict[str, Any]:
    """Build migration-compatibility-report legal hold extension."""

    transitions = [evaluate_legal_hold_migration(scenario, profile=profile) for scenario in scenarios]
    findings = [finding for item in transitions for finding in item.get("findings", [])]
    return {
        "schema_version": "HATE/v1",
        "record_type": "migration-compatibility-report",
        "target_version": "HATE/v1",
        "decisions": [item["compatibility_decision"] for item in transitions],
        "legal_hold_transitions": transitions,
        "findings": findings,
        "summary": {
            "transition_count": len(transitions),
            "preserved_count": sum(1 for item in transitions if item["legal_hold_preserved"]),
            "blocked_count": sum(1 for item in transitions if item["readiness_effect"] == "hard_dq"),
            "readiness_effect": _max_effect(item["readiness_effect"] for item in transitions),
        },
        "sourceRefs": sorted({ref for item in transitions for ref in item.get("sourceRefs", [])}),
    }


def _bundle_from_state(state: dict[str, Any]) -> dict[str, Any]:
    bundle = {
        "schema_version": state.get("schema_version", "HATE/v1"),
        "bundle_id": state.get("bundle_id") or state.get("resource_id", ""),
        "sourceRefs": state.get("sourceRefs", []),
        "legal_hold": state.get("legal_hold"),
    }
    if state.get("source_hash"):
        bundle["source_hash"] = state["source_hash"]
    if state.get("source_mutated"):
        bundle["source_mutated"] = True
    return bundle


def _blocked_operation(operation: str) -> str:
    if operation == "export":
        return "export_raw"
    if operation in {"purge", "delete", "retention_transition"}:
        return "purge"
    return operation


def _operation_attempts_hold_blocked_mutation(operation: str, after: dict[str, Any], legal_hold: dict[str, Any]) -> bool:
    if operation == "retention_transition":
        return after.get("retention_action") in {"purge", "delete"} and legal_hold_blocks_operation(legal_hold, "purge")
    return legal_hold_blocks_operation(legal_hold, _blocked_operation(operation))


def _finding(code: str, effect: str, message: str, source_refs: list[str]) -> dict[str, Any]:
    return {
        "code": code,
        "severity": "critical" if effect == "hard_dq" else "high",
        "readiness_effect": effect,
        "message": message,
        "sourceRef": source_refs[0] if source_refs else "",
    }


def _max_effect(effects: Any) -> str:
    order = {"pass": 0, "soft_gap": 1, "hold": 2, "hard_dq": 3}
    return max(effects, key=lambda item: order.get(item, 0), default="pass")
