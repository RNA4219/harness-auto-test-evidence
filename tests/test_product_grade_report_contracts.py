from __future__ import annotations

import json
from pathlib import Path

from hate.schema_validator import build_schema_validation_report, validate_records
from hate.store.compare import ArtifactDiff, ComparisonReport, ComparisonResult
from hate.store.doctor import DiagnosisFinding, DiagnosisSeverity, DoctorReport
from hate.store.replay import BaselineInfo, ReplayReport, build_store_replay_report


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas" / "HATE" / "v1"
REGISTRY = SCHEMAS / "schema-registry.json"


def test_schema_validation_report_schema_matches_builder_contract() -> None:
    report = build_schema_validation_report(validate_records([]), fixture_id="contract-empty")
    schema = json.loads((SCHEMAS / "schema-validation-report.schema.json").read_text(encoding="utf-8"))

    assert report["record_type"] == schema["properties"]["record_type"]["const"]
    assert report["schema_version"] == schema["properties"]["schema_version"]["const"]
    for field in schema["required"]:
        assert field in report


def test_store_replay_report_schema_matches_replay_report_contract() -> None:
    report = build_store_replay_report(ReplayReport(bundle_id="bundle-1", run_id="run-1"))
    schema = json.loads((SCHEMAS / "store-replay-report.schema.json").read_text(encoding="utf-8"))

    assert report["record_type"] == schema["properties"]["record_type"]["const"]
    assert report["schema_version"] == schema["properties"]["schema_version"]["const"]
    for field in schema["required"]:
        assert field in report
    assert report["baseline_resolution"]["valid"] is True
    assert report["diff_entries"] == []
    assert report["corruption_findings"] == []
    assert report["migration_status"]["compatibility_class"] == "compatible"


def test_store_replay_report_embeds_diff_corruption_migration_and_baseline() -> None:
    comparison = ComparisonReport(
        bundle_id="bundle-current",
        run_id="run-1",
        baseline_bundle_id="bundle-base",
        baseline_selection_method="manifest_timestamp",
        artifact_diffs=[
            ArtifactDiff(
                artifact_id="artifact-1",
                baseline_hash="old",
                current_hash="new",
                result=ComparisonResult.REGRESSION,
                details={"reason": "hash_difference"},
            )
        ],
        regressions=1,
    )
    doctor = DoctorReport(
        diagnosis_scope="single_bundle",
        bundle_id="bundle-current",
        hard_dq_count=1,
        findings=[
            DiagnosisFinding(
                finding_id="F001",
                severity=DiagnosisSeverity.HARD_DQ,
                category="artifact",
                message="Hash mismatch",
                path="artifacts/a.json",
                remediation="Rebuild artifact from canonical bundle",
            )
        ],
    )
    baseline = BaselineInfo(
        baseline_bundle_id="bundle-base",
        baseline_run_id="run-1",
        baseline_created_at="2026-01-01T00:00:00Z",
        selection_method="manifest_timestamp",
        is_filename_sort=False,
    )

    report = build_store_replay_report(
        ReplayReport(bundle_id="bundle-current", run_id="run-1", hash_mismatches=1),
        comparison_report=comparison,
        doctor_report=doctor,
        migration_report={
            "compatibility_class": "migration_required",
            "readiness_effect": "hold",
            "rollback_plan_ref": "docs/migration/rollback.md",
            "checksum_before": "before",
            "checksum_after": "after",
        },
        baseline_info=baseline,
    )

    assert report["readiness_effect"] == "hard_dq"
    assert report["diff_entries"][0]["result"] == "regression"
    assert report["corruption_findings"][0]["severity"] == "hard_dq"
    assert report["migration_status"]["migration_hold"] is True
    assert report["baseline_resolution"]["selection_method"] == "manifest_timestamp"
    assert "src/hate/store/compare.py" in report["sourceRefs"]


def test_product_grade_required_report_schemas_are_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["schema_validation_report"] == "schemas/HATE/v1/schema-validation-report.schema.json"
    assert records["store_replay_report"] == "schemas/HATE/v1/store-replay-report.schema.json"
    assert records["test_integrity_report"] == "schemas/HATE/v1/test-integrity-report.schema.json"
    assert records["security-quarantine-report"] == "schemas/HATE/v1/security-quarantine-report.schema.json"


def test_product_grade_required_schema_files_exist() -> None:
    required_filenames = [
        "adapter-conformance-report.schema.json",
        "schema-validation-report.schema.json",
        "store-replay-report.schema.json",
        "api-contract-report.schema.json",
        "dashboard-uat-report.schema.json",
        "test-integrity-report.schema.json",
        "security-quarantine-report.schema.json",
        "enterprise-control-report.schema.json",
        "scale-performance-report.schema.json",
        "migration-compatibility-report.schema.json",
        "commercial-truthfulness-report.schema.json",
        "support-ops-report.schema.json",
        "release-candidate-pack.schema.json",
    ]

    for filename in required_filenames:
        assert (SCHEMAS / filename).exists(), f"missing product-grade report schema: {filename}"
