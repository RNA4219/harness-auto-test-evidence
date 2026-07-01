"""Tests for adapter manifest validation and conformance reports."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hate.adapter_registry import (
    build_conformance_report,
    load_manifest,
    load_manifests,
    validate_manifest,
)


FIXTURE_ROOT = Path("fixtures/adapters/sdk")
SCHEMA_ROOT = Path("schemas/HATE/v1")


def fixture_path(name: str, filename: str = "manifest.json") -> Path:
    return FIXTURE_ROOT / name / filename


def codes(findings: object) -> set[str]:
    return {finding.code for finding in findings}


def test_schema_documents_publish_required_contract_keys() -> None:
    manifest_schema = json.loads((SCHEMA_ROOT / "adapter-manifest.schema.json").read_text(encoding="utf-8"))
    report_schema = json.loads((SCHEMA_ROOT / "adapter-conformance-report.schema.json").read_text(encoding="utf-8"))

    assert "adapter_id" in manifest_schema["required"]
    assert "parser_entrypoint" in manifest_schema["required"]
    assert "conformance_fixtures" in manifest_schema["required"]
    assert "parserVersion" in report_schema["required"]
    assert "entries" in report_schema["required"]
    assert "sourceRefs" in report_schema["properties"]["entries"]["items"]["required"]


def test_valid_manifest_fixture_loads_and_validates_cleanly() -> None:
    path = fixture_path("valid-manifest")
    manifest = load_manifest(path)
    findings = validate_manifest(manifest, source_ref=str(path))

    assert manifest["adapter_id"] == "pytest-json"
    assert manifest["emitted_record_kinds"] == ["test_result"]
    assert findings == []


def test_missing_required_manifest_field_is_reported_with_source_ref() -> None:
    path = fixture_path("missing-required")
    findings = validate_manifest(load_manifest(path), source_ref=str(path))

    assert codes(findings) == {"missing_required"}
    assert any("parser_entrypoint" in finding.source_ref for finding in findings)


def test_unsupported_schema_versions_are_hard_manifest_findings() -> None:
    path = fixture_path("unsupported-schema-version")
    findings = validate_manifest(load_manifest(path), source_ref=str(path))

    assert {"unsupported_manifest_schema", "unsupported_schema_version"} <= codes(findings)


def test_unknown_output_record_is_rejected() -> None:
    path = fixture_path("unknown-output-record")
    findings = validate_manifest(load_manifest(path), source_ref=str(path))

    assert "unknown_output_record" in codes(findings)
    assert any("unknown_record" in finding.message for finding in findings)


def test_fixture_expected_records_must_match_declared_emitted_records() -> None:
    path = fixture_path("capability-mismatch")
    findings = validate_manifest(load_manifest(path), source_ref=str(path))

    assert "capability_mismatch" in codes(findings)
    assert any("coverage_slice" in finding.message for finding in findings)


def test_duplicate_adapter_ids_are_reported_across_manifest_set() -> None:
    first = fixture_path("duplicate-adapter-id", "first.json")
    second = fixture_path("duplicate-adapter-id", "second.json")

    manifests, findings = load_manifests([first, second])

    assert [manifest["adapter_id"] for manifest in manifests] == ["duplicate", "duplicate"]
    assert "duplicate_adapter_id" in codes(findings)


def test_load_manifest_rejects_non_object_json(tmp_path: Path) -> None:
    path = tmp_path / "array.json"
    path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="manifest must be a JSON object"):
        load_manifest(path)


def test_conformance_report_for_valid_manifest_contains_traceable_entries() -> None:
    manifest = load_manifest(fixture_path("valid-manifest"))
    report = build_conformance_report([manifest], parser_version="adapter-registry/test")

    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "adapter-conformance-report"
    assert report["manifest_id"] == "adapter-sdk-manifest-set"
    assert report["parserVersion"] == "adapter-registry/test"
    assert report["result"] == "pass"
    assert report["status"] == "pass"
    assert report["readiness_effect"] == "none"
    assert report["findings"] == []
    assert report["required_family_count"] == 1
    assert report["observed_family_count"] == 1
    assert report["family_summaries"] == []
    assert report["sourceRefs"] == ["manifest:pytest-json:conformance_fixtures.happy"]
    assert report["entries"] == [
        {
            "adapter_id": "pytest-json",
            "fixture_id": "happy",
            "result": "pass",
            "severity": "pass",
            "sourceRefs": ["manifest:pytest-json:conformance_fixtures.happy"],
            "parserVersion": "adapter-registry/test",
            "produced_record_counts": {"test_result": 0},
        }
    ]


def test_conformance_report_carries_manifest_findings() -> None:
    path = fixture_path("unknown-output-record")
    manifest = load_manifest(path)
    findings = validate_manifest(manifest, source_ref=str(path))

    report = build_conformance_report([manifest], manifest_findings=findings)

    assert report["result"] == "fail"
    assert report["status"] == "hold"
    assert report["readiness_effect"] == "hold"
    assert any(finding["code"] == "unknown_output_record" for finding in report["findings"])
    assert all(finding["readiness_effect"] == "hold" for finding in report["findings"])
    assert any(str(path) in finding["sourceRef"] for finding in report["findings"])
