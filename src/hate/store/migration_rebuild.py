"""Store migration and index rebuild evaluation for HATE-GAP-006."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


LIFECYCLE_STATES = {
    "planned",
    "dry_run",
    "backup_created",
    "migrating",
    "verifying",
    "complete",
    "blocked",
    "rollback",
    "restored",
    "failed",
}
COMPATIBILITY_CLASSES = {"compatible", "migration_required", "unsupported", "blocked"}


@dataclass(frozen=True)
class StoreMigrationFinding:
    code: str
    severity: str
    message: str
    sourceRef: str
    readiness_effect: str = "hold"

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "sourceRef": self.sourceRef,
            "readiness_effect": self.readiness_effect,
        }


def evaluate_store_migration_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    """Evaluate a product-gap fixture and return a store migration report."""

    input_data = payload.get("input", {})
    source_refs = [payload.get("fixture_id", "fixture")]
    report = build_store_migration_report(input_data, source_refs=source_refs)
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_store_migration_report(
    input_data: dict[str, Any],
    *,
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    """Build a deterministic migration/rebuild report from explicit payload fields."""

    data = dict(input_data)
    checkpoint = _normalize_checkpoint(data.get("rebuild_checkpoint"))
    source_refs = _source_refs(data, source_refs or [])
    lifecycle_state = _lifecycle_state(data)
    compatibility_class = _compatibility_class(data)
    findings = _findings_for(data, checkpoint, lifecycle_state, compatibility_class)
    status = "hold" if findings else "pass"

    return {
        "schema_version": "HATE/v1",
        "record_type": "store-migration-report",
        "migration_id": _stable_migration_id(data),
        "from_schema": data.get("from_schema", "HATE/v1"),
        "to_schema": data.get("to_schema", "HATE/v1"),
        "compatibility_class": compatibility_class,
        "lifecycle_state": lifecycle_state,
        "source_bundle_hash_before": data.get("source_bundle_hash_before", ""),
        "source_bundle_hash_after": data.get("source_bundle_hash_after", data.get("source_bundle_hash_before", "")),
        "derived_store_hash_before": data.get("derived_store_hash_before", ""),
        "derived_store_hash_after": data.get("derived_store_hash_after", ""),
        "backup_manifest_ref": data.get("backup_manifest_ref") or "",
        "rollback_report_ref": data.get("rollback_report_ref") or "",
        "replay_verification_ref": data.get("replay_verification_ref") or _default_replay_ref(data),
        "repair_artifact_ref": data.get("repair_artifact_ref") or "",
        "index_state": data.get("index_state", "fresh"),
        "index_rebuild_checkpoints": [checkpoint] if checkpoint else [],
        "findings": [finding.to_dict() for finding in findings],
        "status": status,
        "readiness_effect": "hold" if findings else "none",
        "sourceRefs": source_refs,
    }


def _findings_for(
    data: dict[str, Any],
    checkpoint: dict[str, Any] | None,
    lifecycle_state: str,
    compatibility_class: str,
) -> list[StoreMigrationFinding]:
    findings: list[StoreMigrationFinding] = []
    source_ref = _primary_source_ref(data)
    before = data.get("source_bundle_hash_before")
    after = data.get("source_bundle_hash_after", before)

    if before and after and before != after and not data.get("repair_artifact_ref"):
        findings.append(StoreMigrationFinding(
            code="store_canonical_hash_changed",
            severity="critical",
            message="Canonical source bundle hash changed without an explicit repair artifact.",
            sourceRef=source_ref,
        ))

    if data.get("index_state") == "corrupt" and not checkpoint:
        findings.append(StoreMigrationFinding(
            code="store_index_corrupt_rebuild_required",
            severity="high",
            message="Corrupt index must emit a rebuild checkpoint before readiness can pass.",
            sourceRef=source_ref,
        ))

    if checkpoint:
        expected = checkpoint.get("expected_output_hash")
        output = checkpoint.get("output_hash")
        if expected and output != expected:
            findings.append(StoreMigrationFinding(
                code="store_index_rebuild_hash_mismatch",
                severity="high",
                message="Index rebuild checkpoint output hash does not match the expected hash.",
                sourceRef=str(checkpoint.get("sourceRef") or source_ref),
            ))
        if data.get("index_state") == "partial" and data.get("api_index_fresh") is True:
            findings.append(StoreMigrationFinding(
                code="store_index_partial_marked_fresh",
                severity="high",
                message="Partial rebuild cannot be exposed as a fresh hosted API index.",
                sourceRef=str(checkpoint.get("sourceRef") or source_ref),
            ))

    if lifecycle_state == "failed" and not data.get("rollback_report_ref"):
        findings.append(StoreMigrationFinding(
            code="store_rollback_report_required",
            severity="high",
            message="Failed migration after backup creation requires a rollback report.",
            sourceRef=source_ref,
        ))

    if lifecycle_state == "restored" and not _rollback_hashes_match(data):
        findings.append(StoreMigrationFinding(
            code="store_rollback_hash_mismatch",
            severity="high",
            message="Rollback must restore derived store hash to the pre-migration value.",
            sourceRef=data.get("rollback_report_ref") or source_ref,
        ))

    if _legal_hold_lost(data):
        findings.append(StoreMigrationFinding(
            code="store_rollback_legal_hold_lost",
            severity="critical",
            message="Rollback cannot lose legal hold or retention metadata.",
            sourceRef=data.get("rollback_report_ref") or source_ref,
        ))

    if compatibility_class in {"unsupported", "blocked"}:
        findings.append(StoreMigrationFinding(
            code="store_schema_version_unsupported",
            severity="high",
            message="Schema version skew requires a structured migration policy before use.",
            sourceRef=source_ref,
        ))

    if lifecycle_state == "complete" and not data.get("replay_verification_ref") and data.get("replay") != "pass":
        findings.append(StoreMigrationFinding(
            code="store_replay_verification_missing",
            severity="high",
            message="Complete migration requires replay verification evidence.",
            sourceRef=source_ref,
        ))

    return findings


def _normalize_checkpoint(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    checkpoint = {
        "sequence": raw.get("sequence", 0),
        "input_hash": raw.get("input_hash", ""),
        "output_hash": raw.get("output_hash", ""),
        "expected_output_hash": raw.get("expected_output_hash", ""),
        "record_count": raw.get("record_count", 0),
        "sourceRef": raw.get("sourceRef", "index-rebuild-checkpoints.jsonl"),
    }
    return checkpoint


def _stable_migration_id(data: dict[str, Any]) -> str:
    explicit = data.get("migration_id")
    if explicit:
        return str(explicit)
    from_schema = str(data.get("from_schema", "HATE/v1")).replace("/", "-")
    to_schema = str(data.get("to_schema", "HATE/v1")).replace("/", "-")
    return f"store-migration-{from_schema}-to-{to_schema}"


def _compatibility_class(data: dict[str, Any]) -> str:
    explicit = data.get("compatibility_class")
    if explicit in COMPATIBILITY_CLASSES:
        return str(explicit)
    if data.get("from_schema", "HATE/v1") == data.get("to_schema"):
        return "compatible"
    if data.get("dry_run") is True or data.get("replay") == "pass":
        return "migration_required"
    return "compatible"


def _lifecycle_state(data: dict[str, Any]) -> str:
    explicit = data.get("lifecycle_state")
    if explicit in LIFECYCLE_STATES:
        return str(explicit)
    if data.get("dry_run") is True and data.get("replay") == "pass":
        return "complete"
    if data.get("compatibility_class") in {"unsupported", "blocked"}:
        return "blocked"
    return "planned"


def _source_refs(data: dict[str, Any], explicit_refs: list[str]) -> list[str]:
    refs = list(explicit_refs)
    for key in (
        "migration_plan_ref",
        "dry_run_report_ref",
        "backup_manifest_ref",
        "rollback_report_ref",
        "replay_verification_ref",
        "repair_artifact_ref",
    ):
        value = data.get(key)
        if value:
            refs.append(str(value))
    checkpoint = _normalize_checkpoint(data.get("rebuild_checkpoint"))
    if checkpoint and checkpoint.get("sourceRef"):
        refs.append(str(checkpoint["sourceRef"]))
    return sorted(set(refs))


def _primary_source_ref(data: dict[str, Any]) -> str:
    return str(
        data.get("migration_plan_ref")
        or data.get("dry_run_report_ref")
        or data.get("backup_manifest_ref")
        or "store-migration-input"
    )


def _default_replay_ref(data: dict[str, Any]) -> str:
    if data.get("replay") == "pass":
        return "replay-verification-report.json"
    return ""


def _rollback_hashes_match(data: dict[str, Any]) -> bool:
    before = data.get("derived_store_hash_before")
    after = data.get("derived_store_hash_after")
    return bool(before and after and before == after)


def _legal_hold_lost(data: dict[str, Any]) -> bool:
    before = data.get("legal_hold_before")
    after = data.get("legal_hold_after")
    if isinstance(before, dict) and isinstance(after, dict):
        return before != after
    return before is True and after is False
