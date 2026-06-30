"""Tests for HATE-GAP-006 store migration and index rebuild contract."""

from __future__ import annotations

import json
from pathlib import Path

from hate.store import build_store_migration_report, evaluate_store_migration_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "store" / "migration"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "store-migration-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    required = set(schema["required"])

    assert required <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "store-migration-report"
    assert report["migration_id"]
    assert report["compatibility_class"] in schema["properties"]["compatibility_class"]["enum"]
    assert report["lifecycle_state"] in schema["properties"]["lifecycle_state"]["enum"]
    assert report["status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    assert isinstance(report["sourceRefs"], list)

    for checkpoint in report["index_rebuild_checkpoints"]:
        assert {"sequence", "input_hash", "output_hash", "expected_output_hash", "record_count", "sourceRef"} <= set(
            checkpoint
        )
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_forward_compatible_dry_run_and_replay_pass() -> None:
    result = evaluate_store_migration_fixture(_fixture("forward-compatible"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    report = result["report"]
    _assert_report_contract(report)
    assert report["lifecycle_state"] == "complete"
    assert report["compatibility_class"] == "migration_required"
    assert report["replay_verification_ref"] == "replay-verification-report.json"


def test_rollback_required_on_verification_failure() -> None:
    result = evaluate_store_migration_fixture(_fixture("rollback-required"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "store_rollback_report_required"
    report = result["report"]
    _assert_report_contract(report)
    assert report["backup_manifest_ref"] == "backup-manifest.json"
    assert report["rollback_report_ref"] == ""


def test_corrupt_index_requires_rebuild_checkpoint() -> None:
    result = evaluate_store_migration_fixture(_fixture("corrupt-index"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "store_index_corrupt_rebuild_required"
    assert result["report"]["index_rebuild_checkpoints"] == []


def test_unsupported_future_schema_is_structured_hold() -> None:
    result = evaluate_store_migration_fixture(_fixture("version-skew-denied"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "store_schema_version_unsupported"
    assert result["report"]["compatibility_class"] == "unsupported"


def test_checkpoint_hash_mismatch_is_hold() -> None:
    result = evaluate_store_migration_fixture(_fixture("rebuild-checkpoint-hash-mismatch"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "store_index_rebuild_hash_mismatch"
    checkpoint = result["report"]["index_rebuild_checkpoints"][0]
    assert checkpoint["sequence"] == 3
    assert checkpoint["output_hash"] != checkpoint["expected_output_hash"]


def test_canonical_hash_mutation_is_hard_hold() -> None:
    result = evaluate_store_migration_fixture(_fixture("canonical-hash-changed"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "store_canonical_hash_changed"
    finding = result["report"]["findings"][0]
    assert finding["severity"] == "critical"


def test_rollback_cannot_lose_legal_hold_metadata() -> None:
    report = build_store_migration_report(
        {
            "migration_id": "legal-hold-rollback",
            "lifecycle_state": "restored",
            "backup_manifest_ref": "backup-manifest.json",
            "rollback_report_ref": "rollback-report.json",
            "source_bundle_hash_before": "sha256:canonical-a",
            "source_bundle_hash_after": "sha256:canonical-a",
            "derived_store_hash_before": "sha256:derived-a",
            "derived_store_hash_after": "sha256:derived-a",
            "legal_hold_before": {"hold_id": "LH-001", "retention": "locked"},
            "legal_hold_after": {},
        },
        source_refs=["inline-legal-hold"],
    )

    assert report["status"] == "hold"
    assert report["findings"][0]["code"] == "store_rollback_legal_hold_lost"
    assert report["findings"][0]["severity"] == "critical"


def test_migration_report_includes_source_refs_and_hashes() -> None:
    report = build_store_migration_report(
        {
            "migration_id": "restore-success",
            "lifecycle_state": "restored",
            "backup_manifest_ref": "backup-manifest.json",
            "rollback_report_ref": "rollback-report.json",
            "source_bundle_hash_before": "sha256:canonical-a",
            "source_bundle_hash_after": "sha256:canonical-a",
            "derived_store_hash_before": "sha256:derived-a",
            "derived_store_hash_after": "sha256:derived-a",
        },
        source_refs=["migration-plan.json"],
    )

    _assert_report_contract(report)
    assert report["status"] == "pass"
    assert report["source_bundle_hash_before"] == report["source_bundle_hash_after"]
    assert report["derived_store_hash_before"] == report["derived_store_hash_after"]
    assert "migration-plan.json" in report["sourceRefs"]
    assert "backup-manifest.json" in report["sourceRefs"]
    assert "rollback-report.json" in report["sourceRefs"]


def test_partial_index_cannot_be_marked_fresh() -> None:
    report = build_store_migration_report(
        {
            "index_state": "partial",
            "api_index_fresh": True,
            "rebuild_checkpoint": {
                "sequence": 1,
                "input_hash": "sha256:canonical-a",
                "expected_output_hash": "sha256:index-a",
                "output_hash": "sha256:index-a",
                "record_count": 10,
                "sourceRef": "index-rebuild-checkpoints.jsonl#1",
            },
        }
    )

    assert report["status"] == "hold"
    assert report["findings"][0]["code"] == "store_index_partial_marked_fresh"


def test_store_migration_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["store-migration-report"] == "schemas/HATE/v1/store-migration-report.schema.json"
