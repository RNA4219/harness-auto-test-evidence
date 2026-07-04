from __future__ import annotations

import json
from pathlib import Path

from hate.post_poc.store_dr import (
    build_store_dr_report,
    build_store_dr_runbook,
    evaluate_store_dr_fixture,
    write_store_dr_runbook,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "post-poc" / "dr"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "store-dr-report.schema.json"
RUNBOOK_SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "store-dr-runbook.schema.json"
RUNBOOK_STEP_SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "store-dr-runbook-step.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "store-dr-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    assert report["backup_operation"]["record_type"] == "store-backup-operation"
    assert report["restore_operation"]["record_type"] == "store-restore-operation"
    assert report["dr_drill_result"]["record_type"] == "store-dr-drill-result"
    for field in [
        "backup_id",
        "backup_manifest_ref",
        "created_at",
        "source_store_hash",
        "backup_hash",
        "restore_hash",
        "legal_hold_count_before",
        "legal_hold_count_after",
        "rpo_seconds",
        "rto_seconds",
        "corruption_scan_result",
        "projection_rebuild_status",
    ]:
        assert field in report["dr_drill_result"] or field in report["backup_operation"] or field in report["restore_operation"]
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def _assert_runbook_contract(runbook: dict) -> None:
    schema = json.loads(RUNBOOK_SCHEMA.read_text(encoding="utf-8"))
    step_schema = json.loads(RUNBOOK_STEP_SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(runbook)
    assert runbook["schema_version"] == "HATE/v1"
    assert runbook["record_type"] == "store-dr-runbook"
    assert set(schema["properties"]["summary"]["required"]) <= set(runbook["summary"])
    for step in runbook["steps"]:
        assert set(schema["properties"]["steps"]["items"]["required"]) <= set(step)
        assert set(step_schema["required"]) <= set(step)
        assert step["record_type"] == "store-dr-runbook-step"
        assert step["status"] in {"ready", "blocked"}
    for finding in runbook["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_task_postpoc_012_canonical_fixture_paths_exist() -> None:
    for name in [
        "backup-restore-success",
        "corrupt-backup-denied",
        "legal-hold-lost",
        "rto-exceeded",
        "projection-rebuild-failed",
    ]:
        assert (FIXTURES / name / "fixture.json").is_file()


def test_backup_restore_success_preserves_legal_hold_and_rebuilds_projection() -> None:
    result = evaluate_store_dr_fixture(_fixture("backup-restore-success"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["report"]["summary"]["legal_hold_preserved"] is True
    assert result["report"]["summary"]["rto_budget_status"] == "within_budget"
    assert result["report"]["dr_drill_result"]["projection_rebuild_status"] == "complete"
    _assert_report_contract(result["report"])


def test_corrupt_backup_is_denied_before_canonical_evidence() -> None:
    result = evaluate_store_dr_fixture(_fixture("corrupt-backup-denied"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "dr_corrupt_backup_denied"
    assert result["report"]["restore_operation"]["restore_status"] == "denied"
    assert result["report"]["summary"]["corruption_scan_result"] == "failed"


def test_legal_hold_loss_holds_restore() -> None:
    result = evaluate_store_dr_fixture(_fixture("legal-hold-lost"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "dr_legal_hold_lost"
    assert result["report"]["summary"]["legal_hold_preserved"] is False


def test_rto_exceeded_holds_dr_drill() -> None:
    result = evaluate_store_dr_fixture(_fixture("rto-exceeded"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "dr_restore_rto_exceeded"
    assert result["report"]["summary"]["rto_budget_status"] == "exceeded"


def test_projection_rebuild_failure_holds_dr_drill() -> None:
    result = evaluate_store_dr_fixture(_fixture("projection-rebuild-failed"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "dr_projection_rebuild_failed"
    assert result["report"]["summary"]["projection_rebuild_status"] == "failed"


def test_backup_inventory_missing_holds() -> None:
    report = build_store_dr_report({
        "operation": {
            "backup_id": "",
            "backup_manifest_ref": "",
            "created_at": "",
            "source_store_hash": "sha256:store-ok",
            "backup_hash": "sha256:store-ok",
            "restore_hash": "sha256:store-ok",
            "legal_hold_count_before": 1,
            "legal_hold_count_after": 1,
            "rpo_seconds": 30,
            "rpo_budget_seconds": 300,
            "rto_seconds": 60,
            "rto_budget_seconds": 900,
            "corruption_scan_result": "pass",
            "projection_rebuild_status": "complete",
        }
    })

    assert report["overall_status"] == "hold"
    assert "dr_backup_inventory_missing" in _codes(report)


def test_backup_hash_mismatch_holds() -> None:
    report = build_store_dr_report({
        "operation": {
            "backup_id": "backup-mismatch",
            "backup_manifest_ref": "artifact://store/backups/backup-mismatch/manifest.json",
            "created_at": "2026-07-03T02:00:00Z",
            "source_store_hash": "sha256:store-ok",
            "backup_hash": "sha256:store-different",
            "restore_hash": "sha256:store-ok",
            "legal_hold_count_before": 1,
            "legal_hold_count_after": 1,
            "rpo_seconds": 30,
            "rpo_budget_seconds": 300,
            "rto_seconds": 60,
            "rto_budget_seconds": 900,
            "corruption_scan_result": "pass",
            "projection_rebuild_status": "complete",
        }
    })

    assert report["overall_status"] == "hold"
    assert "dr_backup_hash_mismatch" in _codes(report)


def test_store_dr_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["store-dr-report"] == "schemas/HATE/v1/store-dr-report.schema.json"
    assert records["store-dr-runbook"] == "schemas/HATE/v1/store-dr-runbook.schema.json"
    assert records["store-dr-runbook-step"] == "schemas/HATE/v1/store-dr-runbook-step.schema.json"


def test_store_dr_runbook_ready_for_successful_restore() -> None:
    runbook = build_store_dr_runbook(_fixture("backup-restore-success")["input"], source_refs=["fixture://dr/runbook-ready"])

    assert runbook["record_type"] == "store-dr-runbook"
    _assert_runbook_contract(runbook)
    assert runbook["summary"]["ready_for_restore"] is True
    assert runbook["summary"]["blocked_step_count"] == 0
    assert runbook["findings"] == []
    assert {step["status"] for step in runbook["steps"]} == {"ready"}
    assert runbook["sourceRefs"] == ["fixture://dr/runbook-ready"]


def test_store_dr_runbook_blocks_corrupt_backup() -> None:
    runbook = build_store_dr_runbook(_fixture("corrupt-backup-denied")["input"])

    assert runbook["summary"]["ready_for_restore"] is False
    blocked_steps = [step["step_id"] for step in runbook["steps"] if step["status"] == "blocked"]
    assert "verify_corruption_scan" in blocked_steps
    assert "restore_store" in blocked_steps
    assert "dr_runbook_blocked_by_report_findings" in _codes(runbook)


def test_store_dr_runbook_blocks_rto_exceeded() -> None:
    runbook = build_store_dr_runbook(_fixture("rto-exceeded")["input"])

    assert runbook["summary"]["ready_for_restore"] is False
    blocked_steps = [step["step_id"] for step in runbook["steps"] if step["status"] == "blocked"]
    assert "verify_rto" in blocked_steps


def test_store_dr_runbook_blocks_projection_rebuild_failure() -> None:
    runbook = build_store_dr_runbook(_fixture("projection-rebuild-failed")["input"])

    assert runbook["summary"]["ready_for_restore"] is False
    blocked_steps = [step["step_id"] for step in runbook["steps"] if step["status"] == "blocked"]
    assert "rebuild_projection" in blocked_steps


def test_store_dr_runbook_artifact_write_contract(tmp_path: Path) -> None:
    runbook = build_store_dr_runbook(_fixture("backup-restore-success")["input"], source_refs=["fixture://dr/runbook-artifact"])
    out_path = tmp_path / "store-dr-runbook.json"

    artifact = write_store_dr_runbook(runbook, out_path)

    assert artifact["record_type"] == "store-dr-runbook-artifact"
    assert artifact["step_count"] == len(runbook["steps"])
    assert artifact["sourceRefs"] == ["fixture://dr/runbook-artifact"]
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["record_type"] == "store-dr-runbook"
    _assert_runbook_contract(written)
    assert written["summary"]["ready_for_restore"] is True
