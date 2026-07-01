"""Tests for platform store schema, migration, backup, and restore reports."""

from __future__ import annotations

import json
from pathlib import Path

from hate.p0a_schema import _validate_schema_value
from hate.platform_store_schema import build_platform_store_schema_report


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "platform" / "store"
SCHEMAS = ROOT / "schemas" / "HATE" / "v1"


def test_platform_store_schema_fixture_paths_exist() -> None:
    for name in [
        "minimal-local-jsonl",
        "projection-rebuild-gap",
        "migration-preserves-legal-hold",
        "backup-restore-checksum",
        "orphan-artifact-metadata",
    ]:
        assert (FIXTURES / name / "fixture.json").exists()


def test_minimal_local_jsonl_store_passes() -> None:
    fixture = _fixture("minimal-local-jsonl")

    report = build_platform_store_schema_report(fixture["input"], fixture["fixture_id"])

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert report["summary"]["table_count"] == fixture["expected"]["table_count"]
    assert report["summary"]["index_count"] == fixture["expected"]["index_count"]
    assert report["findings"] == []
    assert "fixtures/platform/store/minimal-local-jsonl/fixture.json#evt-1" in report["sourceRefs"]


def test_projection_rebuild_gap_produces_rebuild_failure() -> None:
    fixture = _fixture("projection-rebuild-gap")

    report = build_platform_store_schema_report(fixture["input"], fixture["fixture_id"])

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert fixture["expected"]["finding_code"] in _codes(report)


def test_migration_preserves_legal_hold_and_raw_access_audit() -> None:
    fixture = _fixture("migration-preserves-legal-hold")

    report = build_platform_store_schema_report(fixture["input"], fixture["fixture_id"])

    assert report["migration_decision"]["legal_hold_preserved"] is fixture["expected"]["legal_hold_preserved"]
    assert report["migration_decision"]["raw_access_audit_preserved"] is fixture["expected"]["raw_access_audit_preserved"]
    assert "platform_store_migration_legal_hold_lost" not in _codes(report)
    assert "platform_store_migration_raw_access_audit_removed" not in _codes(report)


def test_backup_restore_checksum_and_projection_match() -> None:
    fixture = _fixture("backup-restore-checksum")

    report = build_platform_store_schema_report(fixture["input"], fixture["fixture_id"])

    assert report["backup_restore_decision"]["checksum_matches"] is fixture["expected"]["checksum_matches"]
    assert report["backup_restore_decision"]["legal_hold_count_matches"] is fixture["expected"]["legal_hold_count_matches"]
    assert "platform_store_restore_checksum_mismatch" not in _codes(report)


def test_orphan_artifact_metadata_is_reported() -> None:
    fixture = _fixture("orphan-artifact-metadata")

    report = build_platform_store_schema_report(fixture["input"], fixture["fixture_id"])

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert fixture["expected"]["finding_code"] in _codes(report)


def test_platform_store_schema_registered() -> None:
    schema = json.loads((SCHEMAS / "platform-store-schema-report.schema.json").read_text(encoding="utf-8"))
    registry = json.loads((SCHEMAS / "schema-registry.json").read_text(encoding="utf-8"))

    assert schema["properties"]["record_type"]["const"] == "platform-store-schema-report"
    assert any(record["record_type"] == "platform-store-schema-report" for record in registry["records"])


def test_platform_store_schema_report_matches_artifact_schema() -> None:
    fixture = _fixture("minimal-local-jsonl")
    report = build_platform_store_schema_report(fixture["input"], fixture["fixture_id"])
    schema = json.loads((SCHEMAS / "platform-store-schema-report.schema.json").read_text(encoding="utf-8"))

    assert _validate_schema_value(report, schema, "$") == []


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> set[str]:
    return {finding["code"] for finding in report["findings"]}
