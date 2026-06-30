"""Tests for HATE-GAP-034 dependency compliance evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from hate.expansion.dependency_compliance import build_dependency_compliance_report, evaluate_dependency_compliance_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "expansion" / "dependency-compliance"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "dependency-compliance-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "dependency-compliance-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_canonical_gap_034_fixture_paths_exist() -> None:
    assert (FIXTURES / "sbom-clean" / "fixture.json").is_file()
    assert (FIXTURES / "denied-license" / "fixture.json").is_file()


def test_sbom_clean_fixture_passes() -> None:
    result = evaluate_dependency_compliance_fixture(_fixture("sbom-clean"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "none"
    _assert_report_contract(result["report"])


def test_denied_license_fixture_holds() -> None:
    result = evaluate_dependency_compliance_fixture(_fixture("denied-license"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "dependency_compliance_denied_license"
    assert result["readiness_effect"] == "hold"
    _assert_report_contract(result["report"])


def test_missing_sbom_holds() -> None:
    report = build_dependency_compliance_report({
        "sbom_present": False,
        "sbom_format": "cyclonedx-json",
        "packages": [],
        "license_policy_defined": True,
        "allowed_licenses": ["Apache-2.0"],
        "denied_licenses": ["GPL-3.0"],
        "vulnerability_policy_defined": True,
        "vulnerability_max_age_days": 30,
        "exceptions": [],
        "provenance_attestation_present": True,
    })

    assert report["overall_status"] == "hold"
    assert "dependency_compliance_sbom_missing" in _codes(report)


def test_unsupported_sbom_format_holds() -> None:
    report = build_dependency_compliance_report({
        "sbom_present": True,
        "sbom_format": "unknown-format",
        "packages": [],
        "license_policy_defined": True,
        "allowed_licenses": ["Apache-2.0"],
        "denied_licenses": ["GPL-3.0"],
        "vulnerability_policy_defined": True,
        "vulnerability_max_age_days": 30,
        "exceptions": [],
        "provenance_attestation_present": True,
    })

    assert report["overall_status"] == "hold"
    assert "dependency_compliance_sbom_format_unsupported" in _codes(report)


def test_missing_license_policy_holds() -> None:
    report = build_dependency_compliance_report({
        "sbom_present": True,
        "sbom_format": "cyclonedx-json",
        "packages": [],
        "license_policy_defined": False,
        "allowed_licenses": [],
        "denied_licenses": [],
        "vulnerability_policy_defined": True,
        "vulnerability_max_age_days": 30,
        "exceptions": [],
        "provenance_attestation_present": True,
    })

    assert report["overall_status"] == "hold"
    assert "dependency_compliance_license_policy_missing" in _codes(report)


def test_missing_provenance_attestation_holds() -> None:
    report = build_dependency_compliance_report({
        "sbom_present": True,
        "sbom_format": "cyclonedx-json",
        "packages": [],
        "license_policy_defined": True,
        "allowed_licenses": ["Apache-2.0"],
        "denied_licenses": [],
        "vulnerability_policy_defined": True,
        "vulnerability_max_age_days": 30,
        "exceptions": [],
        "provenance_attestation_present": False,
    })

    assert report["overall_status"] == "hold"
    assert "dependency_compliance_provenance_missing" in _codes(report)


def test_dependency_compliance_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["dependency-compliance-report"] == "schemas/HATE/v1/dependency-compliance-report.schema.json"


def test_dependency_compliance_no_report_json_alias_schema() -> None:
    alias_path = ROOT / "schemas" / "HATE" / "v1" / "dependency-compliance-report.json"
    assert not alias_path.exists()