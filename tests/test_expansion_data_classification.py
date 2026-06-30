"""Tests for HATE-GAP-032 data classification evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from hate.expansion.data_classification import build_data_classification_report, evaluate_data_classification_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "expansion" / "data-classification"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "data-classification-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "data-classification-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_canonical_gap_032_fixture_paths_exist() -> None:
    assert (FIXTURES / "public-summary-safe" / "fixture.json").is_file()
    assert (FIXTURES / "prohibited-telemetry-denied" / "fixture.json").is_file()


def test_public_summary_safe_fixture_passes() -> None:
    result = evaluate_data_classification_fixture(_fixture("public-summary-safe"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "none"
    _assert_report_contract(result["report"])


def test_prohibited_telemetry_denied_fixture_holds() -> None:
    result = evaluate_data_classification_fixture(_fixture("prohibited-telemetry-denied"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "data_classification_prohibited_telemetry"
    assert result["readiness_effect"] == "hold"
    _assert_report_contract(result["report"])


def test_missing_field_taxonomy_holds() -> None:
    report = build_data_classification_report({
        "field_taxonomy_defined": False,
        "sink_allowlist_defined": True,
        "redaction_policy_defined": True,
        "telemetry_allowed": True,
        "telemetry_destination": "https://telemetry.example.com/v1",
        "public_summary_safe": True,
        "classified_fields": ["user_email"],
        "prohibited_field_exposed": False,
        "sink_type": "telemetry",
    })

    assert report["overall_status"] == "hold"
    assert "data_classification_taxonomy_missing" in _codes(report)


def test_missing_sink_allowlist_holds() -> None:
    report = build_data_classification_report({
        "field_taxonomy_defined": True,
        "sink_allowlist_defined": False,
        "redaction_policy_defined": True,
        "telemetry_allowed": True,
        "telemetry_destination": "https://telemetry.example.com/v1",
        "public_summary_safe": True,
        "classified_fields": ["user_email"],
        "prohibited_field_exposed": False,
        "sink_type": "telemetry",
    })

    assert report["overall_status"] == "hold"
    assert "data_classification_sink_allowlist_missing" in _codes(report)


def test_missing_redaction_policy_holds() -> None:
    report = build_data_classification_report({
        "field_taxonomy_defined": True,
        "sink_allowlist_defined": True,
        "redaction_policy_defined": False,
        "telemetry_allowed": True,
        "telemetry_destination": "https://telemetry.example.com/v1",
        "public_summary_safe": True,
        "classified_fields": ["user_email"],
        "prohibited_field_exposed": False,
        "sink_type": "telemetry",
    })

    assert report["overall_status"] == "hold"
    assert "data_classification_redaction_missing" in _codes(report)


def test_prohibited_field_exposed_holds() -> None:
    report = build_data_classification_report({
        "field_taxonomy_defined": True,
        "sink_allowlist_defined": True,
        "redaction_policy_defined": True,
        "telemetry_allowed": True,
        "telemetry_destination": "https://telemetry.example.com/v1",
        "public_summary_safe": True,
        "classified_fields": ["user_email"],
        "prohibited_field_exposed": True,
        "sink_type": "telemetry",
    })

    assert report["overall_status"] == "hold"
    assert "data_classification_prohibited_field_exposed" in _codes(report)


def test_data_classification_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["data-classification-report"] == "schemas/HATE/v1/data-classification-report.schema.json"
