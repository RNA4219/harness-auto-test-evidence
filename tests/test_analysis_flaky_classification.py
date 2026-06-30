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


def test_flaky_classification_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["flaky-classification-report"] == "schemas/HATE/v1/flaky-classification-report.schema.json"