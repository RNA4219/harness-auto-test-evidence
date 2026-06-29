"""UAT tests for support diagnostics and product error catalog."""

from __future__ import annotations

import json
from pathlib import Path

from hate.support_ops import (
    build_diagnostic_bundle,
    build_diagnostics_report,
    build_error_catalog_report,
    lookup_error_code,
)


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "support-ops" / "diagnostics"
SUPPORT_SCHEMA = Path(__file__).resolve().parents[1] / "schemas" / "HATE" / "v1" / "support-ops-report.schema.json"
DIAGNOSTIC_SCHEMA = Path(__file__).resolve().parents[1] / "schemas" / "HATE" / "v1" / "safe-diagnostic-bundle.schema.json"


def load_fixture(name: str) -> dict:
    with (FIXTURE_ROOT / name / "fixture.json").open(encoding="utf-8") as f:
        return json.load(f)


def test_packet_fixture_paths_exist() -> None:
    for name in [
        "error-known",
        "safe-diagnostic-bundle",
        "remediation-mapped",
        "raw-artifact-in-bundle",
        "unknown-error-code",
        "missing-owner-action",
    ]:
        assert (FIXTURE_ROOT / name / "fixture.json").exists()


def test_known_error_code_lookup_is_stable() -> None:
    fixture = load_fixture("error-known")
    entry = lookup_error_code(fixture["input"]["error_code"])

    assert entry is not None
    assert entry.error_code == "HATE-ART-003"
    assert entry.remediation
    assert entry.owner_action


def test_safe_diagnostic_bundle_redacts_context_and_keeps_safe_artifacts() -> None:
    fixture = load_fixture("safe-diagnostic-bundle")
    result = build_diagnostic_bundle(fixture["input"])
    bundle = result.bundle
    serialized = json.dumps(bundle, sort_keys=True)

    assert bundle["record_type"] == "safe-diagnostic-bundle"
    assert bundle["export_ready"] is True
    assert bundle["included_artifacts"][0]["artifact_id"] == "artifact-safe-001"
    assert "C:\\Users\\ryo-n" not in serialized
    assert "tok_live_secret" not in serialized
    assert "[REDACTED_PATH]" in serialized
    assert "[REDACTED_SECRET]" in serialized


def test_remediation_mapping_creates_owner_action() -> None:
    fixture = load_fixture("remediation-mapped")
    report = build_error_catalog_report(fixture["input"]["findings"])

    assert report["summary"]["readiness_effect"] == "pass"
    assert report["error_records"][0]["error_code"] == "HATE-DQ-007"
    assert report["error_records"][0]["remediation"]
    assert report["error_records"][0]["owner_action"]


def test_raw_artifact_is_excluded_and_blocks_export_ready() -> None:
    fixture = load_fixture("raw-artifact-in-bundle")
    result = build_diagnostic_bundle(fixture["input"])
    bundle = result.bundle
    serialized = json.dumps(bundle, sort_keys=True)

    assert bundle["export_ready"] is False
    assert bundle["safe_for_summary"] is False
    assert bundle["excluded_artifacts"][0]["reason"] == "raw_field_present"
    assert "customer source code" not in serialized
    assert result.findings[0]["code"] == "raw_artifact_in_diagnostic_bundle"


def test_unknown_error_code_is_hold_not_pass() -> None:
    fixture = load_fixture("unknown-error-code")
    report = build_error_catalog_report(fixture["input"]["findings"])

    assert report["summary"]["readiness_effect"] == "hold"
    assert report["findings"][0]["code"] == "unknown_error_code"
    assert report["error_records"] == []


def test_missing_owner_action_in_catalog_is_detectable() -> None:
    fixture = load_fixture("missing-owner-action")
    result = build_diagnostic_bundle(fixture["input"])

    assert result.findings
    assert result.findings[0]["code"] == "unknown_error_code"
    assert result.bundle["readiness_effect"] == "hold"


def test_diagnostics_report_contains_support_ops_sections() -> None:
    fixture = load_fixture("safe-diagnostic-bundle")
    report = build_diagnostics_report(fixture["input"])

    assert report["record_type"] == "support-ops-report"
    assert report["overall_status"] == "pass"
    assert report["diagnostic_bundles"]
    assert report["summary"]["safe_for_support"] is True


def test_schemas_define_diagnostics_and_error_records() -> None:
    support_schema = json.loads(SUPPORT_SCHEMA.read_text(encoding="utf-8"))
    diagnostic_schema = json.loads(DIAGNOSTIC_SCHEMA.read_text(encoding="utf-8"))

    assert "diagnostic_bundles" in support_schema["properties"]
    assert "error_records" in support_schema["properties"]
    assert "support_error_record" in support_schema["$defs"]
    assert "included_artifacts" in diagnostic_schema["properties"]
    assert "excluded_artifacts" in diagnostic_schema["properties"]
