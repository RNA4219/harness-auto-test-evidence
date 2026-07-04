"""Tests for HATE-GAP-051 flaky classification evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from hate.analysis.flaky_classification import (
    build_flaky_classification_report,
    evaluate_flaky_classification_fixture,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "expansion" / "flaky-classification"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "flaky-classification-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "flaky-classification-report"
    assert report["overall_status"] in {"pass", "hold", "blocked"}
    assert report["readiness_effect"] in {"none", "hold", "blocked"}
    assert "classified_tests" in report
    assert "flaky_classification_diagnostics" in report
    assert {
        "classified_test_count",
        "unknown_flake_count",
        "mixed_outcome_test_count",
        "duplicate_attempt_count",
    } <= set(report["summary"])
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_canonical_gap_051_fixture_paths_exist() -> None:
    assert (FIXTURES / "environment-flake-classified" / "fixture.json").is_file()
    assert (FIXTURES / "unknown-flake-hold" / "fixture.json").is_file()


def test_environment_flake_classified_fixture_passes() -> None:
    result = evaluate_flaky_classification_fixture(_fixture("environment-flake-classified"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "none"
    _assert_report_contract(result["report"])


def test_unknown_flake_hold_fixture_holds() -> None:
    result = evaluate_flaky_classification_fixture(_fixture("unknown-flake-hold"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "flaky_classification_unknown_flake_hold"
    assert result["readiness_effect"] == "hold"
    _assert_report_contract(result["report"])


def test_environment_evidence_missing_holds() -> None:
    report = build_flaky_classification_report({
        "flake_classes": [{"class_id": "c1", "class_name": "env", "confidence": 0.9, "sourceRef": "c:1", "rationale": "r", "verified": True}],
        "attempt_history": [{"attempt_id": "a1", "test_id": "t1", "outcome": "fail", "confidence": 0.9, "sourceRef": "a:1", "rationale": "r"}],
        "environment_evidence": [{"evidence_id": "e1", "delta_type": "runtime", "confidence": 0.9, "sourceRef": "e:1", "rationale": "r", "verified": True}],
        "class_taxonomy_available": True,
        "retry_history_available": True,
        "environment_evidence_available": False,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "flaky_classification_environment_evidence_missing" in _codes(report)


def test_retry_history_missing_holds() -> None:
    report = build_flaky_classification_report({
        "flake_classes": [{"class_id": "c1", "class_name": "env", "confidence": 0.9, "sourceRef": "c:1", "rationale": "r", "verified": True}],
        "attempt_history": [{"attempt_id": "a1", "test_id": "t1", "outcome": "fail", "confidence": 0.9, "sourceRef": "a:1", "rationale": "r"}],
        "environment_evidence": [{"evidence_id": "e1", "delta_type": "runtime", "confidence": 0.9, "sourceRef": "e:1", "rationale": "r", "verified": True}],
        "class_taxonomy_available": True,
        "retry_history_available": False,
        "environment_evidence_available": True,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "flaky_classification_retry_history_missing" in _codes(report)


def test_unverified_flake_class_holds() -> None:
    report = build_flaky_classification_report({
        "flake_classes": [{"class_id": "c1", "class_name": "env", "confidence": 0.9, "sourceRef": "c:1", "rationale": "r", "verified": False}],
        "attempt_history": [{"attempt_id": "a1", "test_id": "t1", "outcome": "fail", "confidence": 0.9, "sourceRef": "a:1", "rationale": "r"}],
        "environment_evidence": [{"evidence_id": "e1", "delta_type": "runtime", "confidence": 0.9, "sourceRef": "e:1", "rationale": "r", "verified": True}],
        "class_taxonomy_available": True,
        "retry_history_available": True,
        "environment_evidence_available": True,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "flaky_classification_unknown_flake_hold" in _codes(report)


def test_flaky_source_availability_defaults_to_hold() -> None:
    report = build_flaky_classification_report({
        "flake_classes": [{"class_id": "c1", "class_name": "env", "confidence": 0.9, "sourceRef": "c:1", "rationale": "r", "verified": True}],
        "attempt_history": [{"attempt_id": "a1", "test_id": "t1", "outcome": "fail", "confidence": 0.9, "sourceRef": "a:1", "rationale": "r"}],
        "environment_evidence": [{"evidence_id": "e1", "delta_type": "runtime", "confidence": 0.9, "sourceRef": "e:1", "rationale": "r", "verified": True}],
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert {
        "flaky_classification_unknown_flake_hold",
        "flaky_classification_retry_history_missing",
        "flaky_classification_environment_evidence_missing",
    }.issubset(set(_codes(report)))


def test_environment_evidence_without_source_ref_holds() -> None:
    report = build_flaky_classification_report({
        "flake_classes": [{"class_id": "c1", "class_name": "env", "confidence": 0.9, "sourceRef": "c:1", "rationale": "r", "verified": True}],
        "attempt_history": [{"attempt_id": "a1", "test_id": "t1", "outcome": "fail", "confidence": 0.9, "sourceRef": "a:1", "rationale": "r"}],
        "environment_evidence": [{"evidence_id": "e1", "delta_type": "runtime", "confidence": 0.9, "sourceRef": "", "rationale": "r", "verified": True}],
        "class_taxonomy_available": True,
        "retry_history_available": True,
        "environment_evidence_available": True,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "flaky_classification_environment_evidence_missing" in _codes(report)


def test_attempt_without_source_ref_holds() -> None:
    report = build_flaky_classification_report({
        "flake_classes": [{"class_id": "c1", "class_name": "env", "confidence": 0.9, "sourceRef": "c:1", "rationale": "r", "verified": True}],
        "attempt_history": [{"attempt_id": "a1", "test_id": "t1", "outcome": "fail", "confidence": 0.9, "sourceRef": "", "rationale": "r"}],
        "environment_evidence": [{"evidence_id": "e1", "delta_type": "runtime", "confidence": 0.9, "sourceRef": "e:1", "rationale": "r", "verified": True}],
        "class_taxonomy_available": True,
        "retry_history_available": True,
        "environment_evidence_available": True,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "flaky_classification_retry_history_missing" in _codes(report)


def test_mixed_outcome_with_environment_delta_is_classified_not_held() -> None:
    report = build_flaky_classification_report({
        "flake_classes": [{"class_id": "c1", "class_name": "environment", "confidence": 0.9, "sourceRef": "c:1", "rationale": "r", "verified": True}],
        "attempt_history": [
            {"attempt_id": "a1", "test_id": "t1", "outcome": "failed", "confidence": 0.9, "sourceRef": "a:1", "rationale": "runtime drift"},
            {"attempt_id": "a2", "test_id": "t1", "outcome": "passed", "confidence": 0.9, "sourceRef": "a:2", "rationale": "runtime stable"},
        ],
        "environment_evidence": [{"evidence_id": "e1", "delta_type": "runtime_version", "confidence": 0.9, "sourceRef": "e:1", "rationale": "r", "verified": True}],
        "class_taxonomy_available": True,
        "retry_history_available": True,
        "environment_evidence_available": True,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "pass"
    assert report["classified_tests"]["t1"]["class_name"] == "environment"
    assert report["summary"]["mixed_outcome_test_count"] == 1


def test_unknown_mixed_outcome_holds() -> None:
    report = build_flaky_classification_report({
        "flake_classes": [{"class_id": "c1", "class_name": "unknown", "confidence": 0.9, "sourceRef": "c:1", "rationale": "r", "verified": True}],
        "attempt_history": [
            {"attempt_id": "a1", "test_id": "t1", "outcome": "failed", "confidence": 0.9, "sourceRef": "a:1", "rationale": "nondiagnostic"},
            {"attempt_id": "a2", "test_id": "t1", "outcome": "passed", "confidence": 0.9, "sourceRef": "a:2", "rationale": "nondiagnostic"},
        ],
        "environment_evidence": [],
        "class_taxonomy_available": True,
        "retry_history_available": True,
        "environment_evidence_available": True,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "flaky_classification_unknown_flake_hold" in _codes(report)
    assert "flaky_classification_mixed_outcome_detected" in _codes(report)


def test_timeout_and_infrastructure_are_classified_from_attempt_text() -> None:
    timeout_report = build_flaky_classification_report({
        "flake_classes": [{"class_id": "c1", "class_name": "timeout", "confidence": 0.9, "sourceRef": "c:1", "rationale": "r", "verified": True}],
        "attempt_history": [
            {"attempt_id": "a1", "test_id": "timeout-test", "outcome": "timeout", "error_signature": "TimeoutError", "confidence": 0.9, "sourceRef": "a:1", "rationale": ""},
            {"attempt_id": "a2", "test_id": "timeout-test", "outcome": "passed", "confidence": 0.9, "sourceRef": "a:2", "rationale": ""},
        ],
        "environment_evidence": [],
        "class_taxonomy_available": True,
        "retry_history_available": True,
        "environment_evidence_available": True,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })
    infra_report = build_flaky_classification_report({
        "flake_classes": [{"class_id": "c1", "class_name": "infrastructure", "confidence": 0.9, "sourceRef": "c:1", "rationale": "r", "verified": True}],
        "attempt_history": [
            {"attempt_id": "a1", "test_id": "net-test", "outcome": "failed", "error_signature": "ECONNRESET connection reset", "confidence": 0.9, "sourceRef": "a:1", "rationale": ""},
            {"attempt_id": "a2", "test_id": "net-test", "outcome": "passed", "confidence": 0.9, "sourceRef": "a:2", "rationale": ""},
        ],
        "environment_evidence": [],
        "class_taxonomy_available": True,
        "retry_history_available": True,
        "environment_evidence_available": True,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert timeout_report["classified_tests"]["timeout-test"]["class_name"] == "timeout"
    assert infra_report["classified_tests"]["net-test"]["class_name"] == "infrastructure"


def test_duplicate_unverified_and_budget_excess_hold() -> None:
    report = build_flaky_classification_report({
        "flake_classes": [
            {"class_id": "c1", "class_name": "env", "confidence": 0.9, "sourceRef": "c:1", "rationale": "r", "verified": True},
            {"class_id": "c2", "class_name": "timeout", "confidence": 0.9, "sourceRef": "c:2", "rationale": "r", "verified": True},
        ],
        "attempt_history": [
            {"attempt_id": "dup", "test_id": "t1", "outcome": "failed", "confidence": 0.9, "sourceRef": "a:1", "rationale": "runtime"},
            {"attempt_id": "dup", "test_id": "t1", "outcome": "passed", "confidence": 0.9, "sourceRef": "a:2", "rationale": "runtime"},
        ],
        "environment_evidence": [
            {"evidence_id": "e1", "delta_type": "runtime", "confidence": 0.9, "sourceRef": "e:1", "rationale": "r", "verified": False},
            {"evidence_id": "e2", "delta_type": "cache", "confidence": 0.9, "sourceRef": "e:2", "rationale": "r", "verified": True},
        ],
        "class_taxonomy_available": True,
        "retry_history_available": True,
        "environment_evidence_available": True,
        "confidence": 0.9,
        "limits": {
            "confidence_threshold": 0.7,
            "max_flake_classes": 1,
            "max_attempts": 1,
            "max_environment_evidence": 1,
        },
    })

    assert report["overall_status"] == "hold"
    assert "flaky_classification_duplicate_attempt_id" in _codes(report)
    assert "flaky_classification_environment_evidence_missing" in _codes(report)
    assert "flaky_classification_class_budget_exceeded" in _codes(report)
    assert "flaky_classification_attempt_budget_exceeded" in _codes(report)
    assert "flaky_classification_environment_budget_exceeded" in _codes(report)


def test_flaky_classification_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["flaky-classification-report"] == "schemas/HATE/v1/flaky-classification-report.schema.json"
