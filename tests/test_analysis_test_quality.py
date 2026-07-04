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
    assert "test_quality_diagnostics" in report
    assert {
        "test_source_count",
        "duplicate_test_count",
        "source_anti_pattern_count",
        "unverified_pattern_count",
    } <= set(report["summary"])
    assert {
        "duplicate_test_ids",
        "source_anti_patterns",
        "large_fixture_test_ids",
        "overbroad_snapshot_test_ids",
        "unverified_pattern_ids",
    } <= set(report["test_quality_diagnostics"])
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


def test_quality_support_availability_defaults_to_hold() -> None:
    report = build_test_quality_report({
        "test_patterns": [{"pattern_id": "tp1", "pattern_type": "deterministic", "quality_dimension": "reliability", "confidence": 0.9, "sourceRef": "tp:1", "rationale": "r", "verified": True}],
        "anti_patterns": [{"anti_pattern_id": "ap1", "anti_pattern_type": "sleep_based", "severity": "low", "confidence": 0.9, "sourceRef": "ap:1", "rationale": "r", "mitigated": True}],
        "quality_metrics": [{"metric_id": "qm1", "metric_type": "determinism", "value": 0.9, "confidence": 0.9, "sourceRef": "qm:1", "rationale": "r"}],
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert {
        "test_quality_determinism_missing",
        "test_quality_timeout_missing",
        "test_quality_isolation_missing",
    }.issubset(set(_codes(report)))


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


def test_source_text_anti_patterns_are_inferred() -> None:
    report = build_test_quality_report({
        "test_patterns": [{"pattern_id": "tp1", "pattern_type": "deterministic", "quality_dimension": "reliability", "confidence": 0.9, "sourceRef": "tp:1", "rationale": "r", "verified": True}],
        "anti_patterns": [],
        "quality_metrics": [{"metric_id": "qm1", "metric_type": "determinism", "value": 0.9, "confidence": 0.9, "sourceRef": "qm:1", "rationale": "r"}],
        "test_sources": [
            {
                "test_id": "test_unstable",
                "sourceRef": "tests/test_unstable.py:1",
                "text": "time.sleep(1); value = random.random(); requests.get('https://example.invalid')",
            }
        ],
        "determinism_available": True,
        "timeout_available": True,
        "isolation_available": True,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "test_quality_sleep_based_test_hold" in _codes(report)
    assert "test_quality_random_usage_hold" in _codes(report)
    assert "test_quality_network_usage_hold" in _codes(report)
    assert report["test_quality_diagnostics"]["source_anti_patterns"]["test_unstable"] == [
        "sleep_based",
        "random_usage",
        "network_usage",
    ]


def test_duplicate_test_ids_and_order_dependence_hold() -> None:
    report = build_test_quality_report({
        "test_patterns": [{"pattern_id": "tp1", "pattern_type": "deterministic", "quality_dimension": "reliability", "confidence": 0.9, "sourceRef": "tp:1", "rationale": "r", "verified": True}],
        "anti_patterns": [],
        "quality_metrics": [{"metric_id": "qm1", "metric_type": "determinism", "value": 0.9, "confidence": 0.9, "sourceRef": "qm:1", "rationale": "r"}],
        "test_sources": [
            {"test_id": "test_flow", "sourceRef": "tests/test_flow.py:1", "text": "shared_state['x'] = 1"},
            {"test_id": "test_flow", "sourceRef": "tests/test_flow.py:2", "text": "assert shared_state['x'] == 1"},
        ],
        "determinism_available": True,
        "timeout_available": True,
        "isolation_available": True,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "test_quality_duplicate_test_detected" in _codes(report)
    assert "test_quality_order_dependence_hold" in _codes(report)
    assert report["summary"]["duplicate_test_count"] == 1


def test_huge_fixture_and_overbroad_snapshot_hold() -> None:
    report = build_test_quality_report({
        "test_patterns": [{"pattern_id": "tp1", "pattern_type": "snapshot", "quality_dimension": "oracle", "confidence": 0.9, "sourceRef": "tp:1", "rationale": "r", "verified": True}],
        "anti_patterns": [],
        "quality_metrics": [{"metric_id": "qm1", "metric_type": "determinism", "value": 0.9, "confidence": 0.9, "sourceRef": "qm:1", "rationale": "r"}],
        "test_sources": [
            {
                "test_id": "test_big_snapshot",
                "sourceRef": "tests/test_snapshot.py:1",
                "text": "assert snapshot == actual",
                "fixture_size_bytes": 2048,
                "snapshot_line_count": 1000,
            }
        ],
        "determinism_available": True,
        "timeout_available": True,
        "isolation_available": True,
        "confidence": 0.9,
        "limits": {
            "confidence_threshold": 0.7,
            "max_fixture_size_bytes": 1024,
            "max_snapshot_line_count": 250,
        },
    })

    assert report["overall_status"] == "hold"
    assert "test_quality_huge_fixture_hold" in _codes(report)
    assert "test_quality_overbroad_snapshot_hold" in _codes(report)


def test_unverified_pattern_and_budget_excess_hold() -> None:
    report = build_test_quality_report({
        "test_patterns": [
            {"pattern_id": "tp1", "pattern_type": "deterministic", "quality_dimension": "reliability", "confidence": 0.9, "sourceRef": "tp:1", "rationale": "r", "verified": False},
            {"pattern_id": "tp2", "pattern_type": "contract", "quality_dimension": "oracle", "confidence": 0.9, "sourceRef": "tp:2", "rationale": "r", "verified": True},
        ],
        "anti_patterns": [
            {"anti_pattern_id": "ap1", "anti_pattern_type": "sleep_based", "severity": "low", "confidence": 0.9, "sourceRef": "ap:1", "rationale": "r", "mitigated": True},
            {"anti_pattern_id": "ap2", "anti_pattern_type": "random_usage", "severity": "low", "confidence": 0.9, "sourceRef": "ap:2", "rationale": "r", "mitigated": True},
        ],
        "quality_metrics": [
            {"metric_id": "qm1", "metric_type": "determinism", "value": 0.9, "confidence": 0.9, "sourceRef": "qm:1", "rationale": "r"},
            {"metric_id": "qm2", "metric_type": "isolation", "value": 0.9, "confidence": 0.9, "sourceRef": "qm:2", "rationale": "r"},
        ],
        "determinism_available": True,
        "timeout_available": True,
        "isolation_available": True,
        "confidence": 0.9,
        "limits": {
            "confidence_threshold": 0.7,
            "max_test_patterns": 1,
            "max_anti_patterns": 1,
            "max_quality_metrics": 1,
        },
    })

    assert report["overall_status"] == "hold"
    assert "test_quality_unverified_pattern_hold" in _codes(report)
    assert "test_quality_pattern_budget_exceeded" in _codes(report)
    assert "test_quality_anti_pattern_budget_exceeded" in _codes(report)
    assert "test_quality_metric_budget_exceeded" in _codes(report)


def test_test_quality_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["test-quality-report"] == "schemas/HATE/v1/test-quality-report.schema.json"
