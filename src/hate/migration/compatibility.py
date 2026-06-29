"""Schema and bundle migration compatibility dry-run checks."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any


SUPPORTED_TARGET_VERSION = "HATE/v1"
MIGRATION_HOLD_VERSIONS = {"HATE/v0.8", "HATE/v0.9"}
VERSION_PATTERN = re.compile(r"^HATE/v(?P<major>\d+)(?:\.(?P<minor>\d+))?(?:\.(?P<patch>\d+))?$")


@dataclass
class MigrationCompatibilityDecision:
    """Migration compatibility decision for a dry-run candidate."""

    source_version: str
    target_version: str
    decision: str
    readiness_effect: str
    reason: str
    source_hash: str
    migrated_hash: str
    source_refs_preserved: bool = True
    legal_hold_preserved: bool = True
    canonical_source_mutated: bool = False
    findings: list[dict[str, Any]] = field(default_factory=list)
    sourceRefs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_version": self.source_version,
            "target_version": self.target_version,
            "decision": self.decision,
            "readiness_effect": self.readiness_effect,
            "reason": self.reason,
            "source_hash": self.source_hash,
            "migrated_hash": self.migrated_hash,
            "source_refs_preserved": self.source_refs_preserved,
            "legal_hold_preserved": self.legal_hold_preserved,
            "canonical_source_mutated": self.canonical_source_mutated,
            "findings": self.findings,
            "sourceRefs": self.sourceRefs,
        }


def evaluate_migration_compatibility(
    source_bundle: dict[str, Any],
    migrated_bundle: dict[str, Any] | None = None,
    *,
    target_version: str = SUPPORTED_TARGET_VERSION,
    profile: str = "default",
) -> MigrationCompatibilityDecision:
    """Evaluate schema migration compatibility without mutating source bundle."""

    migrated_bundle = migrated_bundle if migrated_bundle is not None else dict(source_bundle)
    source_version = str(source_bundle.get("schema_version") or source_bundle.get("schema_versions", {}).get("bundle") or "")
    source_refs = list(source_bundle.get("sourceRefs") or source_bundle.get("source_refs") or [])
    source_hash = _stable_hash(source_bundle)
    migrated_hash = _stable_hash(migrated_bundle)

    version_decision = _version_decision(source_version, target_version, profile)
    findings = list(version_decision["findings"])
    source_refs_preserved = _source_refs_preserved(source_bundle, migrated_bundle)
    legal_hold_preserved = _legal_hold_preserved(source_bundle, migrated_bundle)
    canonical_source_mutated = bool(source_bundle.get("canonical_source_mutated") or migrated_bundle.get("source_mutated"))

    if not source_refs_preserved:
        findings.append(_finding("source_ref_lost", "hard_dq", "Migration lost sourceRefs.", source_refs))
    if not legal_hold_preserved:
        findings.append(_finding("legal_hold_lost", "hard_dq", "Migration lost legal hold metadata.", source_refs))
    if canonical_source_mutated:
        findings.append(_finding("canonical_source_mutated", "hard_dq", "Migration mutated canonical source bundle.", source_refs))
    if source_hash != str(migrated_bundle.get("source_hash", source_hash)):
        findings.append(_finding("source_hash_mismatch", "hard_dq", "Source hash does not match migration record.", source_refs))

    readiness_effect = _max_effect([version_decision["readiness_effect"]] + [f["readiness_effect"] for f in findings])
    decision = "pass" if readiness_effect == "pass" else ("hold" if readiness_effect == "hold" else "blocked")
    reason = version_decision["reason"] if not findings else findings[0]["code"]

    return MigrationCompatibilityDecision(
        source_version=source_version,
        target_version=target_version,
        decision=decision,
        readiness_effect=readiness_effect,
        reason=reason,
        source_hash=source_hash,
        migrated_hash=migrated_hash,
        source_refs_preserved=source_refs_preserved,
        legal_hold_preserved=legal_hold_preserved,
        canonical_source_mutated=canonical_source_mutated,
        findings=findings,
        sourceRefs=source_refs,
    )


def build_migration_compatibility_report(
    scenarios: list[dict[str, Any]],
    *,
    target_version: str = SUPPORTED_TARGET_VERSION,
    profile: str = "default",
) -> dict[str, Any]:
    """Build a migration-compatibility-report for one or more scenarios."""

    decisions = [
        evaluate_migration_compatibility(
            scenario["source_bundle"],
            scenario.get("migrated_bundle"),
            target_version=scenario.get("target_version", target_version),
            profile=scenario.get("profile", profile),
        ).to_dict()
        for scenario in scenarios
    ]
    findings = [finding for decision in decisions for finding in decision.get("findings", [])]
    return {
        "schema_version": "HATE/v1",
        "record_type": "migration-compatibility-report",
        "target_version": target_version,
        "decisions": decisions,
        "findings": findings,
        "summary": {
            "decision_count": len(decisions),
            "pass_count": sum(1 for item in decisions if item["readiness_effect"] == "pass"),
            "hold_count": sum(1 for item in decisions if item["readiness_effect"] == "hold"),
            "hard_dq_count": sum(1 for item in decisions if item["readiness_effect"] == "hard_dq"),
            "readiness_effect": _max_effect(item["readiness_effect"] for item in decisions),
        },
        "sourceRefs": sorted({ref for decision in decisions for ref in decision.get("sourceRefs", [])}),
    }


def _version_decision(source_version: str, target_version: str, profile: str) -> dict[str, Any]:
    if source_version == target_version:
        return {"readiness_effect": "pass", "reason": "patch_compatible", "findings": []}
    source = _parse_version(source_version)
    target = _parse_version(target_version)
    if not source or not target:
        effect = "hard_dq" if profile in {"release", "regulated"} else "hold"
        return {
            "readiness_effect": effect,
            "reason": "unsupported_schema_version",
            "findings": [_finding("unsupported_schema_version", effect, "Unsupported schema version.", [])],
        }
    if source_version in MIGRATION_HOLD_VERSIONS:
        return {
            "readiness_effect": "hold",
            "reason": "migration_required",
            "findings": [_finding("migration_required", "hold", "Schema version requires migration dry-run.", [])],
        }
    if source["major"] == target["major"] and source["major"] == 1:
        return {"readiness_effect": "pass", "reason": "minor_compatible", "findings": []}
    effect = "hard_dq" if profile in {"release", "regulated"} else "hold"
    return {
        "readiness_effect": effect,
        "reason": "unsupported_major_version",
        "findings": [_finding("unsupported_major_version", effect, "Unsupported major schema version.", [])],
    }


def _parse_version(value: str) -> dict[str, int] | None:
    match = VERSION_PATTERN.match(value)
    if not match:
        return None
    return {
        "major": int(match.group("major")),
        "minor": int(match.group("minor") or 0),
        "patch": int(match.group("patch") or 0),
    }


def _source_refs_preserved(source_bundle: dict[str, Any], migrated_bundle: dict[str, Any]) -> bool:
    source_refs = set(source_bundle.get("sourceRefs") or source_bundle.get("source_refs") or [])
    migrated_refs = set(migrated_bundle.get("sourceRefs") or migrated_bundle.get("source_refs") or [])
    return source_refs.issubset(migrated_refs)


def _legal_hold_preserved(source_bundle: dict[str, Any], migrated_bundle: dict[str, Any]) -> bool:
    source_hold = source_bundle.get("legal_hold")
    if source_hold is None:
        source_hold = source_bundle.get("retention", {}).get("legal_hold")
    migrated_hold = migrated_bundle.get("legal_hold")
    if migrated_hold is None:
        migrated_hold = migrated_bundle.get("retention", {}).get("legal_hold")
    return source_hold == migrated_hold


def _stable_hash(value: dict[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


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
