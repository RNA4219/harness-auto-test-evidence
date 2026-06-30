"""Tests for HATE-GAP-029 bulk portability evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from hate.expansion.bulk_portability import build_bulk_portability_report, evaluate_bulk_portability_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "expansion" / "bulk-portability"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "bulk-portability-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "bulk-portability-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_canonical_gap_029_fixture_paths_exist() -> None:
    assert (FIXTURES / "resumable-export" / "fixture.json").is_file()
    assert (FIXTURES / "cross-tenant-import-denied" / "fixture.json").is_file()


def test_resumable_export_fixture_passes() -> None:
    result = evaluate_bulk_portability_fixture(_fixture("resumable-export"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "none"
    _assert_report_contract(result["report"])


def test_cross_tenant_import_denied_fixture_holds() -> None:
    result = evaluate_bulk_portability_fixture(_fixture("cross-tenant-import-denied"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "bulk_portability_cross_tenant_import_denied"
    assert result["readiness_effect"] == "hold"
    _assert_report_contract(result["report"])


def test_missing_chunk_manifest_holds() -> None:
    report = build_bulk_portability_report({
        "chunk_manifest_defined": False,
        "resume_token_supported": True,
        "integrity_manifest_defined": True,
        "partial_failure_handling": True,
        "tenant_boundary_enforced": True,
        "source_tenant": "tenant-001",
        "target_tenant": "tenant-001",
        "migration_size_mb": 500,
    })

    assert report["overall_status"] == "hold"
    assert "bulk_portability_chunk_manifest_missing" in _codes(report)


def test_missing_resume_token_holds() -> None:
    report = build_bulk_portability_report({
        "chunk_manifest_defined": True,
        "resume_token_supported": False,
        "integrity_manifest_defined": True,
        "partial_failure_handling": True,
        "tenant_boundary_enforced": True,
        "source_tenant": "tenant-001",
        "target_tenant": "tenant-001",
        "migration_size_mb": 500,
    })

    assert report["overall_status"] == "hold"
    assert "bulk_portability_resume_token_missing" in _codes(report)


def test_missing_integrity_manifest_holds() -> None:
    report = build_bulk_portability_report({
        "chunk_manifest_defined": True,
        "resume_token_supported": True,
        "integrity_manifest_defined": False,
        "partial_failure_handling": True,
        "tenant_boundary_enforced": True,
        "source_tenant": "tenant-001",
        "target_tenant": "tenant-001",
        "migration_size_mb": 500,
    })

    assert report["overall_status"] == "hold"
    assert "bulk_portability_integrity_manifest_missing" in _codes(report)


def test_bulk_portability_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["bulk-portability-report"] == "schemas/HATE/v1/bulk-portability-report.schema.json"
