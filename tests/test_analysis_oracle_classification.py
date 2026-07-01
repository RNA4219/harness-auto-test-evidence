"""Tests for HATE-GAP-052 oracle classification evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from hate.analysis.oracle_classification import (
    build_oracle_classification_report,
    evaluate_oracle_classification_fixture,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "expansion" / "oracle-classification"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "oracle-classification-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "oracle-classification-report"
    assert report["overall_status"] in {"pass", "hold", "blocked"}
    assert report["readiness_effect"] in {"none", "hold", "blocked"}
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_canonical_gap_052_fixture_paths_exist() -> None:
    assert (FIXTURES / "property-oracle-pass" / "fixture.json").is_file()
    assert (FIXTURES / "snapshot-only-critical-hold" / "fixture.json").is_file()


def test_property_oracle_fixture_passes() -> None:
    result = evaluate_oracle_classification_fixture(_fixture("property-oracle-pass"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "none"
    _assert_report_contract(result["report"])


def test_snapshot_only_critical_fixture_holds() -> None:
    result = evaluate_oracle_classification_fixture(_fixture("snapshot-only-critical-hold"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "oracle_classification_snapshot_only_critical_hold"
    assert result["readiness_effect"] == "hold"
    _assert_report_contract(result["report"])


def test_critical_risk_without_oracle_holds() -> None:
    report = build_oracle_classification_report({
        "oracle_classes": [{"oracle_id": "o1", "oracle_type": "property", "target_risk": "r1", "confidence": 0.9, "sourceRef": "o:1", "rationale": "r", "verified": True}],
        "semantic_guards": [{"guard_id": "g1", "guard_type": "behavioral", "target_behavior": "b1", "confidence": 0.9, "sourceRef": "g:1", "rationale": "r", "verified": True}],
        "no_oracle_risks": [{"risk_id": "nor1", "risk_type": "critical", "severity": "critical", "confidence": 0.9, "sourceRef": "nor:1", "rationale": "r", "mitigated": False}],
        "oracle_taxonomy_available": True,
        "semantic_guard_available": True,
        "critical_risk_coverage_available": True,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "oracle_classification_no_oracle_for_required_risk" in _codes(report)


def test_semantic_guard_missing_source_ref_holds() -> None:
    report = build_oracle_classification_report({
        "oracle_classes": [{"oracle_id": "o1", "oracle_type": "property", "target_risk": "r1", "confidence": 0.9, "sourceRef": "o:1", "rationale": "r", "verified": True}],
        "semantic_guards": [{"guard_id": "g1", "guard_type": "behavioral", "target_behavior": "b1", "confidence": 0.9, "sourceRef": "", "rationale": "r", "verified": True}],
        "no_oracle_risks": [{"risk_id": "nor1", "risk_type": "low", "severity": "low", "confidence": 0.9, "sourceRef": "nor:1", "rationale": "r", "mitigated": True}],
        "oracle_taxonomy_available": True,
        "semantic_guard_available": True,
        "critical_risk_coverage_available": True,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "oracle_classification_semantic_guard_missing" in _codes(report)


def test_unverified_oracle_class_holds() -> None:
    report = build_oracle_classification_report({
        "oracle_classes": [{"oracle_id": "o1", "oracle_type": "property", "target_risk": "r1", "confidence": 0.9, "sourceRef": "o:1", "rationale": "r", "verified": False}],
        "semantic_guards": [{"guard_id": "g1", "guard_type": "behavioral", "target_behavior": "b1", "confidence": 0.9, "sourceRef": "g:1", "rationale": "r", "verified": True}],
        "no_oracle_risks": [{"risk_id": "nor1", "risk_type": "low", "severity": "low", "confidence": 0.9, "sourceRef": "nor:1", "rationale": "r", "mitigated": True}],
        "oracle_taxonomy_available": True,
        "semantic_guard_available": True,
        "critical_risk_coverage_available": True,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "oracle_classification_snapshot_only_critical_hold" in _codes(report)


def test_oracle_support_availability_defaults_to_hold() -> None:
    report = build_oracle_classification_report({
        "oracle_classes": [{"oracle_id": "o1", "oracle_type": "property", "target_risk": "r1", "confidence": 0.9, "sourceRef": "o:1", "rationale": "r", "verified": True}],
        "semantic_guards": [{"guard_id": "g1", "guard_type": "behavioral", "target_behavior": "b1", "confidence": 0.9, "sourceRef": "g:1", "rationale": "r", "verified": True}],
        "no_oracle_risks": [{"risk_id": "nor1", "risk_type": "low", "severity": "low", "confidence": 0.9, "sourceRef": "nor:1", "rationale": "r", "mitigated": True}],
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert {
        "oracle_classification_taxonomy_missing",
        "oracle_classification_semantic_guard_missing",
        "oracle_classification_critical_coverage_missing",
    }.issubset(set(_codes(report)))


def test_oracle_classification_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["oracle-classification-report"] == "schemas/HATE/v1/oracle-classification-report.schema.json"
