"""Tests for HATE-GAP-059 fixture quality evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from hate.analysis.fixture_quality import (
    build_fixture_quality_report,
    evaluate_fixture_quality_fixture,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "expansion" / "fixture-quality"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "fixture-quality-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "fixture-quality-report"
    assert report["overall_status"] in {"pass", "hold", "blocked"}
    assert report["readiness_effect"] in {"none", "hold", "blocked"}
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_canonical_gap_059_fixture_paths_exist() -> None:
    assert (FIXTURES / "corpus-quality-pass" / "fixture.json").is_file()
    assert (FIXTURES / "fixture-name-coupled-hold" / "fixture.json").is_file()


def test_corpus_quality_fixture_passes() -> None:
    result = evaluate_fixture_quality_fixture(_fixture("corpus-quality-pass"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "none"
    _assert_report_contract(result["report"])


def test_fixture_name_coupled_fixture_holds() -> None:
    result = evaluate_fixture_quality_fixture(_fixture("fixture-name-coupled-hold"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "fixture_quality_fixture_name_coupled_hold"
    assert result["readiness_effect"] == "hold"
    _assert_report_contract(result["report"])


def test_expected_output_exposed_holds() -> None:
    report = build_fixture_quality_report({
        "fixture_findings": [{"fixture_id": "f1", "fixture_type": "positive", "quality_metrics": {}, "sourceRef": "f:1", "rationale": ""}],
        "corpus_scope": {"corpus_id": "c1", "fixture_count": 10, "coverage_target": 0.90, "completeness_baseline": 0.85},
        "schema_drift": {"drift_detected": False, "schema_version": "v1", "baseline_version": "v1", "drift_fields": []},
        "fixture_name_behavior_coupled": False,
        "expected_output_exposed": True,
        "confidence": 0.95,
        "limits": {"confidence_threshold": 0.7, "max_fixture_findings": 50, "coverage_threshold": 0.8},
    })

    assert report["overall_status"] == "hold"
    assert "fixture_quality_expected_output_leakage" in _codes(report)


def test_schema_drift_detected_holds() -> None:
    report = build_fixture_quality_report({
        "fixture_findings": [{"fixture_id": "f1", "fixture_type": "positive", "quality_metrics": {}, "sourceRef": "f:1", "rationale": ""}],
        "corpus_scope": {"corpus_id": "c1", "fixture_count": 10, "coverage_target": 0.90, "completeness_baseline": 0.85},
        "schema_drift": {"drift_detected": True, "schema_version": "v2", "baseline_version": "v1", "drift_fields": ["field1"]},
        "fixture_name_behavior_coupled": False,
        "expected_output_exposed": False,
        "confidence": 0.95,
        "limits": {"confidence_threshold": 0.7, "max_fixture_findings": 50, "coverage_threshold": 0.8},
    })

    assert report["overall_status"] == "hold"
    assert "fixture_quality_schema_drift" in _codes(report)


def test_fixture_finding_without_source_ref_holds() -> None:
    report = build_fixture_quality_report({
        "fixture_findings": [{"fixture_id": "f1", "fixture_type": "positive", "quality_metrics": {}, "sourceRef": "", "rationale": ""}],
        "corpus_scope": {"corpus_id": "c1", "fixture_count": 10, "coverage_target": 0.90, "completeness_baseline": 0.85},
        "schema_drift": {"drift_detected": False, "schema_version": "v1", "baseline_version": "v1", "drift_fields": []},
        "fixture_name_behavior_coupled": False,
        "expected_output_exposed": False,
        "confidence": 0.95,
        "limits": {"confidence_threshold": 0.7, "max_fixture_findings": 50, "coverage_threshold": 0.8},
    })

    assert report["overall_status"] == "hold"
    assert "fixture_quality_fixture_name_coupled_hold" in _codes(report)


def test_coverage_below_threshold_holds() -> None:
    report = build_fixture_quality_report({
        "fixture_findings": [{"fixture_id": "f1", "fixture_type": "positive", "quality_metrics": {}, "sourceRef": "f:1", "rationale": ""}],
        "corpus_scope": {"corpus_id": "c1", "fixture_count": 10, "coverage_target": 0.70, "completeness_baseline": 0.85},
        "schema_drift": {"drift_detected": False, "schema_version": "v1", "baseline_version": "v1", "drift_fields": []},
        "fixture_name_behavior_coupled": False,
        "expected_output_exposed": False,
        "confidence": 0.95,
        "limits": {"confidence_threshold": 0.7, "max_fixture_findings": 50, "coverage_threshold": 0.8},
    })

    assert report["overall_status"] == "hold"
    assert "fixture_quality_fixture_name_coupled_hold" in _codes(report)


def test_confidence_below_threshold_holds() -> None:
    report = build_fixture_quality_report({
        "fixture_findings": [{"fixture_id": "f1", "fixture_type": "positive", "quality_metrics": {}, "sourceRef": "f:1", "rationale": ""}],
        "corpus_scope": {"corpus_id": "c1", "fixture_count": 10, "coverage_target": 0.90, "completeness_baseline": 0.85},
        "schema_drift": {"drift_detected": False, "schema_version": "v1", "baseline_version": "v1", "drift_fields": []},
        "fixture_name_behavior_coupled": False,
        "expected_output_exposed": False,
        "confidence": 0.5,
        "limits": {"confidence_threshold": 0.7, "max_fixture_findings": 50, "coverage_threshold": 0.8},
    })

    assert report["overall_status"] == "hold"
    assert "fixture_quality_fixture_name_coupled_hold" in _codes(report)


def test_fixture_quality_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["fixture-quality-report"] == "schemas/HATE/v1/fixture-quality-report.schema.json"