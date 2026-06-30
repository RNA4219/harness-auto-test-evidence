"""Tests for HATE-GAP-054 test quality evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from hate.analysis.test_quality import (
    build_test_quality_report,
    evaluate_test_quality_fixture,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "expansion" / "test-quality"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "test-quality-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "test-quality-report"
    assert report["overall_status"] in {"pass", "hold", "blocked"}
    assert report["readiness_effect"] in {"none", "hold", "blocked"}
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_canonical_gap_054_fixture_paths_exist() -> None:
    assert (FIXTURES / "deterministic-tests-pass" / "fixture.json").is_file()
    assert (FIXTURES / "sleep-based-test-hold" / "fixture.json").is_file()


def test_deterministic_tests_fixture_passes() -> None:
    result = evaluate_test_quality_fixture(_fixture("deterministic-tests-pass"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "none"
    _assert_report_contract(result["report"])


def test_sleep_based_test_fixture_holds() -> None:
    result = evaluate_test_quality_fixture(_fixture("sleep-based-test-hold"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "test_quality_sleep_based_test_hold"
    assert result["readiness_effect"] == "hold"
    _assert_report_contract(result["report"])


def test_determinism_missing_holds() -> None:
    report = build_test_quality_report({
        "test_patterns": [{"pattern_id": "tp1", "pattern_type": "deterministic", "quality_dimension": "reliability", "confidence": 0.9, "sourceRef": "tp:1", "rationale": "r", "verified": True}],
        "anti_patterns": [{"anti_pattern_id": "ap1", "anti_pattern_type": "sleep_based", "severity": "low", "confidence": 0.9, "sourceRef": "ap:1", "rationale": "r", "mitigated": True}],
        "quality_metrics": [{"metric_id": "qm1", "metric_type": "determinism", "value": 0.9, "confidence": 0.9, "sourceRef": "qm:1", "rationale": "r"}],
        "determinism_available": False,
        "timeout_available": True,
        "isolation_available": True,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "test_quality_determinism_missing" in _codes(report)


def test_timeout_missing_holds() -> None:
    report = build_test_quality_report({
        "test_patterns": [{"pattern_id": "tp1", "pattern_type": "deterministic", "quality_dimension": "reliability", "confidence": 0.9, "sourceRef": "tp:1", "rationale": "r", "verified": True}],
        "anti_patterns": [{"anti_pattern_id": "ap1", "anti_pattern_type": "sleep_based", "severity": "low", "confidence": 0.9, "sourceRef": "ap:1", "rationale": "r", "mitigated": True}],
        "quality_metrics": [{"metric_id": "qm1", "metric_type": "determinism", "value": 0.9, "confidence": 0.9, "sourceRef": "qm:1", "rationale": "r"}],
        "determinism_available": True,
        "timeout_available": False,
        "isolation_available": True,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "test_quality_timeout_missing" in _codes(report)


def test_isolation_missing_holds() -> None:
    report = build_test_quality_report({
        "test_patterns": [{"pattern_id": "tp1", "pattern_type": "deterministic", "quality_dimension": "reliability", "confidence": 0.9, "sourceRef": "tp:1", "rationale": "r", "verified": True}],
        "anti_patterns": [{"anti_pattern_id": "ap1", "anti_pattern_type": "sleep_based", "severity": "low", "confidence": 0.9, "sourceRef": "ap:1", "rationale": "r", "mitigated": True}],
        "quality_metrics": [{"metric_id": "qm1", "metric_type": "determinism", "value": 0.9, "confidence": 0.9, "sourceRef": "qm:1", "rationale": "r"}],
        "determinism_available": True,
        "timeout_available": True,
        "isolation_available": False,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "test_quality_isolation_missing" in _codes(report)


def test_critical_anti_pattern_not_mitigated_holds() -> None:
    report = build_test_quality_report({
        "test_patterns": [{"pattern_id": "tp1", "pattern_type": "deterministic", "quality_dimension": "reliability", "confidence": 0.9, "sourceRef": "tp:1", "rationale": "r", "verified": True}],
        "anti_patterns": [{"anti_pattern_id": "ap1", "anti_pattern_type": "sleep_based", "severity": "critical", "confidence": 0.9, "sourceRef": "ap:1", "rationale": "r", "mitigated": False}],
        "quality_metrics": [{"metric_id": "qm1", "metric_type": "determinism", "value": 0.9, "confidence": 0.9, "sourceRef": "qm:1", "rationale": "r"}],
        "determinism_available": True,
        "timeout_available": True,
        "isolation_available": True,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "test_quality_sleep_based_test_hold" in _codes(report)


def test_anti_pattern_without_source_ref_holds() -> None:
    report = build_test_quality_report({
        "test_patterns": [{"pattern_id": "tp1", "pattern_type": "deterministic", "quality_dimension": "reliability", "confidence": 0.9, "sourceRef": "tp:1", "rationale": "r", "verified": True}],
        "anti_patterns": [{"anti_pattern_id": "ap1", "anti_pattern_type": "sleep_based", "severity": "low", "confidence": 0.9, "sourceRef": "", "rationale": "r", "mitigated": True}],
        "quality_metrics": [{"metric_id": "qm1", "metric_type": "determinism", "value": 0.9, "confidence": 0.9, "sourceRef": "qm:1", "rationale": "r"}],
        "determinism_available": True,
        "timeout_available": True,
        "isolation_available": True,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "test_quality_sleep_based_test_hold" in _codes(report)


def test_pattern_without_source_ref_holds() -> None:
    report = build_test_quality_report({
        "test_patterns": [{"pattern_id": "tp1", "pattern_type": "deterministic", "quality_dimension": "reliability", "confidence": 0.9, "sourceRef": "", "rationale": "r", "verified": True}],
        "anti_patterns": [{"anti_pattern_id": "ap1", "anti_pattern_type": "sleep_based", "severity": "low", "confidence": 0.9, "sourceRef": "ap:1", "rationale": "r", "mitigated": True}],
        "quality_metrics": [{"metric_id": "qm1", "metric_type": "determinism", "value": 0.9, "confidence": 0.9, "sourceRef": "qm:1", "rationale": "r"}],
        "determinism_available": True,
        "timeout_available": True,
        "isolation_available": True,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "test_quality_determinism_missing" in _codes(report)


def test_test_quality_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["test-quality-report"] == "schemas/HATE/v1/test-quality-report.schema.json"