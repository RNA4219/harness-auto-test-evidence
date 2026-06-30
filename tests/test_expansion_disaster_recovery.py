"""Tests for HATE-GAP-037 disaster recovery evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from hate.expansion.disaster_recovery import build_disaster_recovery_report, evaluate_disaster_recovery_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "expansion" / "disaster-recovery"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "disaster-recovery-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "disaster-recovery-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_canonical_gap_037_fixture_paths_exist() -> None:
    assert (FIXTURES / "restore-drill-pass" / "fixture.json").is_file()
    assert (FIXTURES / "corrupt-backup-denied" / "fixture.json").is_file()


def test_restore_drill_pass_fixture_passes() -> None:
    result = evaluate_disaster_recovery_fixture(_fixture("restore-drill-pass"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "none"
    _assert_report_contract(result["report"])


def test_corrupt_backup_denied_fixture_holds() -> None:
    result = evaluate_disaster_recovery_fixture(_fixture("corrupt-backup-denied"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "disaster_recovery_corrupt_backup_denied"
    assert result["readiness_effect"] == "hold"
    _assert_report_contract(result["report"])


def test_missing_backup_inventory_holds() -> None:
    report = build_disaster_recovery_report({
        "backup_inventory_present": False,
        "backup_id": "backup-001",
        "backup_created_at": "2026-07-01T00:00:00Z",
        "backup_integrity_hash": "sha256:abc123",
        "restore_drill_executed": True,
        "restore_verified": True,
        "rpo_minutes": 60,
        "rto_minutes": 120,
        "rpo_budget_minutes": 240,
        "rto_budget_minutes": 480,
        "corrupt_backup_detected": False,
        "incident_evidence_present": True,
    })

    assert report["overall_status"] == "hold"
    assert "disaster_recovery_backup_inventory_missing" in _codes(report)


def test_missing_restore_drill_holds() -> None:
    report = build_disaster_recovery_report({
        "backup_inventory_present": True,
        "backup_id": "backup-001",
        "backup_created_at": "2026-07-01T00:00:00Z",
        "backup_integrity_hash": "sha256:abc123",
        "restore_drill_executed": False,
        "restore_verified": True,
        "rpo_minutes": 60,
        "rto_minutes": 120,
        "rpo_budget_minutes": 240,
        "rto_budget_minutes": 480,
        "corrupt_backup_detected": False,
        "incident_evidence_present": True,
    })

    assert report["overall_status"] == "hold"
    assert "disaster_recovery_restore_drill_missing" in _codes(report)


def test_rpo_exceeded_holds() -> None:
    report = build_disaster_recovery_report({
        "backup_inventory_present": True,
        "backup_id": "backup-001",
        "backup_created_at": "2026-07-01T00:00:00Z",
        "backup_integrity_hash": "sha256:abc123",
        "restore_drill_executed": True,
        "restore_verified": True,
        "rpo_minutes": 300,
        "rto_minutes": 120,
        "rpo_budget_minutes": 240,
        "rto_budget_minutes": 480,
        "corrupt_backup_detected": False,
        "incident_evidence_present": True,
    })

    assert report["overall_status"] == "hold"
    assert "disaster_recovery_rpo_exceeded" in _codes(report)


def test_rto_exceeded_holds() -> None:
    report = build_disaster_recovery_report({
        "backup_inventory_present": True,
        "backup_id": "backup-001",
        "backup_created_at": "2026-07-01T00:00:00Z",
        "backup_integrity_hash": "sha256:abc123",
        "restore_drill_executed": True,
        "restore_verified": True,
        "rpo_minutes": 60,
        "rto_minutes": 600,
        "rpo_budget_minutes": 240,
        "rto_budget_minutes": 480,
        "corrupt_backup_detected": False,
        "incident_evidence_present": True,
    })

    assert report["overall_status"] == "hold"
    assert "disaster_recovery_rto_exceeded" in _codes(report)


def test_disaster_recovery_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["disaster-recovery-report"] == "schemas/HATE/v1/disaster-recovery-report.schema.json"