"""Platform store schema, migration, backup, and restore validation."""

from __future__ import annotations

import hashlib
import json
from typing import Any


STORE_MODES = {"local-jsonl", "sqlite", "postgres"}
LOGICAL_TABLES: dict[str, str] = {
    "run_history": "run_id",
    "run_suite_result": "run_id,repo_id,suite_id",
    "score_history": "score_id",
    "baseline_event": "baseline_event_id",
    "operating_event": "event_id",
    "operating_projection": "operating_record_id",
    "policy_snapshot": "policy_hash",
    "plugin_execution": "plugin_execution_id",
    "artifact_metadata": "artifact_id",
    "scheduler_job": "job_id",
    "audit_event": "audit_event_id",
}
REQUIRED_INDEXES = {
    "idx_run_repo_time",
    "idx_run_source_version",
    "idx_suite_status",
    "idx_score_repo_time",
    "idx_operating_status_due",
    "idx_operating_owner",
    "idx_operating_entity",
    "idx_policy_hash",
    "idx_artifact_state",
    "idx_scheduler_state_lease",
}
APPEND_ONLY_TABLES = {"run_history", "score_history", "baseline_event", "operating_event", "audit_event"}


def build_platform_store_schema_report(data: dict[str, Any], report_id: str = "platform-store-schema") -> dict[str, Any]:
    """Validate platform store schema/recovery inputs against the platform spec."""
    findings: list[dict[str, Any]] = []
    store_mode = str(data.get("store_mode") or "")
    tables = _table_map(data.get("tables") or [])
    indexes = _index_names(data.get("indexes", []))
    events = sorted([dict(item) for item in data.get("events", [])], key=lambda item: item.get("sequence", 0))
    migration = dict(data.get("migration") or {})
    backup = dict(data.get("backup_manifest") or {})
    restore = dict(data.get("restore") or {})
    artifacts = [dict(item) for item in data.get("artifact_metadata", [])]

    if store_mode not in STORE_MODES:
        findings.append(_finding("platform_store_mode_unknown", {"store_mode": store_mode}))
    _check_tables(tables, findings)
    _check_indexes(indexes, findings)
    _check_events(events, findings)
    _check_migration(migration, findings)
    _check_backup_restore(backup, restore, artifacts, findings)

    source_refs = _report_source_refs(data, events, migration, backup, restore, artifacts, findings)
    return {
        "schema_version": "HATE/v1",
        "record_type": "platform-store-schema-report",
        "report_id": report_id,
        "overall_status": "hold" if findings else "pass",
        "readiness_effect": "hold" if findings else "none",
        "store_mode": store_mode,
        "logical_tables": _logical_table_summary(tables),
        "required_indexes": sorted(REQUIRED_INDEXES),
        "event_ordering": _event_ordering_summary(events),
        "migration_decision": _migration_summary(migration),
        "backup_restore_decision": _backup_restore_summary(backup, restore, artifacts),
        "findings": findings,
        "summary": {
            "table_count": len(tables),
            "index_count": len(indexes),
            "event_count": len(events),
            "artifact_metadata_count": len(artifacts),
            "finding_count": len(findings),
        },
        "sourceRefs": source_refs,
    }


def _table_map(raw_tables: list[Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in raw_tables:
        if isinstance(item, str):
            result[item] = {"name": item}
        elif isinstance(item, dict):
            name = str(item.get("name") or item.get("table") or "")
            if name:
                result[name] = dict(item)
    return result


def _index_names(raw_indexes: list[Any]) -> set[str]:
    names = set()
    for item in raw_indexes:
        if isinstance(item, str):
            names.add(item)
        elif isinstance(item, dict):
            names.add(str(item.get("name") or item.get("index") or ""))
    return {name for name in names if name}


def _check_tables(tables: dict[str, dict[str, Any]], findings: list[dict[str, Any]]) -> None:
    for table, key in LOGICAL_TABLES.items():
        if table not in tables:
            findings.append(_finding("platform_store_logical_table_missing", {"table": table}))
            continue
        actual_key = str(tables[table].get("key") or "")
        if actual_key and actual_key.replace(" ", "") != key:
            findings.append(_finding("platform_store_logical_table_key_mismatch", {"table": table, "expected_key": key}))


def _check_indexes(indexes: set[str], findings: list[dict[str, Any]]) -> None:
    for index in sorted(REQUIRED_INDEXES - indexes):
        findings.append(_finding("platform_store_required_index_missing", {"index": index}))


def _check_events(events: list[dict[str, Any]], findings: list[dict[str, Any]]) -> None:
    previous_sequence = 0
    previous_hash = ""
    seen_ids: set[str] = set()
    for event in events:
        event_id = str(event.get("event_id") or "")
        sequence = event.get("sequence")
        table = str(event.get("table") or "operating_event")
        if table in APPEND_ONLY_TABLES:
            for field in ["sequence", "event_id", "occurred_at", "actor", "sourceRefs", "previous_event_hash", "event_hash"]:
                if field not in event:
                    findings.append(_finding("platform_store_append_event_field_missing", {"event_id": event_id, "field": field}))
        if event_id in seen_ids:
            findings.append(_finding("platform_store_event_duplicate_id", {"event_id": event_id}))
        seen_ids.add(event_id)
        if isinstance(sequence, int):
            if sequence != previous_sequence + 1:
                findings.append(_finding("projection_rebuild_failed_event_gap", {"event_id": event_id, "sequence": sequence}))
            previous_sequence = sequence
        else:
            findings.append(_finding("platform_store_event_sequence_invalid", {"event_id": event_id}))
        expected_previous = str(event.get("previous_event_hash") or "")
        if previous_hash and expected_previous != previous_hash:
            findings.append(_finding("projection_rebuild_failed_hash_continuity", {"event_id": event_id}))
        previous_hash = str(event.get("event_hash") or "")


def _check_migration(migration: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    if not migration:
        return
    required = [
        "migration_id",
        "from_store_version",
        "to_store_version",
        "started_at",
        "finished_at",
        "status",
        "pre_migration_checksum",
        "post_migration_checksum",
        "rollback_note",
        "compatibility_report_ref",
    ]
    for field in required:
        if not migration.get(field):
            findings.append(_finding("platform_store_migration_field_missing", {"field": field}))
    if migration.get("legal_hold_before_count", 0) != migration.get("legal_hold_after_count", 0):
        findings.append(_finding("platform_store_migration_legal_hold_lost"))
    if migration.get("accepted_debt_expiry_rewritten_without_event"):
        findings.append(_finding("platform_store_migration_debt_expiry_rewritten"))
    if migration.get("score_history_changed_without_original_report"):
        findings.append(_finding("platform_store_migration_score_history_unpreserved"))
    if migration.get("raw_access_audit_before_count", 0) != migration.get("raw_access_audit_after_count", 0):
        findings.append(_finding("platform_store_migration_raw_access_audit_removed"))


def _check_backup_restore(
    backup: dict[str, Any],
    restore: dict[str, Any],
    artifacts: list[dict[str, Any]],
    findings: list[dict[str, Any]],
) -> None:
    if backup:
        for field in ["backup_id", "store_version", "created_at", "table_counts", "artifact_metadata_count", "legal_hold_count", "checksum", "sourceRefs"]:
            if field not in backup:
                findings.append(_finding("platform_store_backup_field_missing", {"field": field}))
    if restore:
        if restore.get("append_only_event_counts_match") is False:
            findings.append(_finding("platform_store_restore_event_count_mismatch"))
        if restore.get("projection_hash_matches") is False:
            findings.append(_finding("platform_store_restore_projection_hash_mismatch"))
        if backup and restore.get("legal_hold_count") != backup.get("legal_hold_count"):
            findings.append(_finding("platform_store_restore_legal_hold_count_mismatch"))
        expected_checksum = backup.get("checksum") if backup else ""
        if expected_checksum and restore.get("checksum") != expected_checksum:
            findings.append(_finding("platform_store_restore_checksum_mismatch"))
    known_refs = set(restore.get("resolved_artifact_refs") or [])
    for artifact in artifacts:
        artifact_id = str(artifact.get("artifact_id") or "")
        if artifact.get("referenced") and artifact_id not in known_refs:
            findings.append(_finding("platform_store_orphan_artifact_metadata", {"artifact_id": artifact_id}))


def _logical_table_summary(tables: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"table": table, "key": key, "present": table in tables}
        for table, key in LOGICAL_TABLES.items()
    ]


def _event_ordering_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "event_count": len(events),
        "sequences": [event.get("sequence") for event in events],
        "projection_hash": _stable_hash(events) if events else "",
    }


def _migration_summary(migration: dict[str, Any]) -> dict[str, Any]:
    return {
        "migration_id": str(migration.get("migration_id") or ""),
        "status": str(migration.get("status") or ""),
        "legal_hold_preserved": migration.get("legal_hold_before_count", 0) == migration.get("legal_hold_after_count", 0),
        "raw_access_audit_preserved": migration.get("raw_access_audit_before_count", 0) == migration.get("raw_access_audit_after_count", 0),
    }


def _backup_restore_summary(backup: dict[str, Any], restore: dict[str, Any], artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "backup_id": str(backup.get("backup_id") or ""),
        "checksum_matches": bool(backup) and backup.get("checksum") == restore.get("checksum"),
        "projection_hash_matches": bool(restore.get("projection_hash_matches", False)),
        "legal_hold_count_matches": bool(backup) and backup.get("legal_hold_count") == restore.get("legal_hold_count"),
        "artifact_metadata_count": len(artifacts),
    }


def _finding(code: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    finding = {
        "code": code,
        "severity": "high",
        "readiness_effect": "hold",
        "message": code,
        "sourceRefs": [],
    }
    if extra:
        finding.update(extra)
    return finding


def _report_source_refs(
    data: dict[str, Any],
    events: list[dict[str, Any]],
    migration: dict[str, Any],
    backup: dict[str, Any],
    restore: dict[str, Any],
    artifacts: list[dict[str, Any]],
    findings: list[dict[str, Any]],
) -> list[str]:
    refs: list[str] = []
    for item in [data, migration, backup, restore, *events, *artifacts, *findings]:
        refs.extend(_source_refs(item))
    return sorted(set(refs))


def _source_refs(item: Any) -> list[str]:
    if not isinstance(item, dict):
        return []
    refs: list[str] = []
    for key in ("sourceRefs", "source_refs"):
        raw = item.get(key)
        if isinstance(raw, list):
            refs.extend(str(ref) for ref in raw if str(ref))
        elif isinstance(raw, str) and raw:
            refs.append(raw)
    raw_ref = item.get("sourceRef") or item.get("source_ref")
    if isinstance(raw_ref, str) and raw_ref:
        refs.append(raw_ref)
    return refs


def _stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
