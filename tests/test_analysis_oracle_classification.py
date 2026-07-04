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
    assert "inferred_oracles" in report
    assert "oracle_classification_diagnostics" in report
    assert {
        "test_source_count",
        "inferred_oracle_count",
        "weak_oracle_count",
        "no_oracle_test_count",
    } <= set(report["summary"])
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


def test_oracle_types_are_inferred_from_test_source() -> None:
    report = build_oracle_classification_report({
        "oracle_classes": [],
        "semantic_guards": [],
        "no_oracle_risks": [],
        "test_sources": [
            {"test_id": "exact", "target_risk": "r1", "severity": "low", "sourceRef": "t:1", "text": "assert result == expected"},
            {"test_id": "property", "target_risk": "r2", "severity": "low", "sourceRef": "t:2", "text": "@given(x=...) property invariant"},
            {"test_id": "metamorphic", "target_risk": "r3", "severity": "low", "sourceRef": "t:3", "text": "roundtrip inverse metamorphic check"},
            {"test_id": "contract", "target_risk": "r4", "severity": "low", "sourceRef": "t:4", "text": "contract schema validation"},
        ],
        "oracle_taxonomy_available": True,
        "semantic_guard_available": True,
        "critical_risk_coverage_available": True,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    inferred = {item["test_id"]: item["oracle_type"] for item in report["inferred_oracles"]}
    assert inferred["exact"] == "exact"
    assert inferred["property"] == "property"
    assert inferred["metamorphic"] == "metamorphic"
    assert inferred["contract"] == "contract"
    assert report["overall_status"] == "pass"


def test_critical_snapshot_truthiness_and_no_oracle_hold() -> None:
    report = build_oracle_classification_report({
        "oracle_classes": [],
        "semantic_guards": [],
        "no_oracle_risks": [],
        "test_sources": [
            {"test_id": "snapshot", "target_risk": "r1", "severity": "critical", "sourceRef": "t:1", "text": "expect(ui).toMatchSnapshot()"},
            {"test_id": "truthy", "target_risk": "r2", "severity": "medium", "sourceRef": "t:2", "text": "assert result"},
            {"test_id": "none", "target_risk": "r3", "severity": "critical", "sourceRef": "t:3", "text": "service.run()"},
        ],
        "oracle_taxonomy_available": True,
        "semantic_guard_available": True,
        "critical_risk_coverage_available": True,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "oracle_classification_snapshot_only_critical_hold" in _codes(report)
    assert "oracle_classification_weak_oracle_hold" in _codes(report)
    assert "oracle_classification_no_oracle_for_required_risk" in _codes(report)
    assert report["summary"]["weak_oracle_count"] == 2
    assert report["summary"]["no_oracle_test_count"] == 1


def test_duplicate_source_ref_and_budget_excess_hold() -> None:
    report = build_oracle_classification_report({
        "oracle_classes": [
            {"oracle_id": "dup", "oracle_type": "exact", "target_risk": "r1", "confidence": 0.9, "sourceRef": "", "rationale": "r", "verified": True},
            {"oracle_id": "dup", "oracle_type": "property", "target_risk": "r2", "confidence": 0.9, "sourceRef": "o:2", "rationale": "r", "verified": True},
        ],
        "semantic_guards": [
            {"guard_id": "g1", "guard_type": "behavioral", "target_behavior": "b1", "confidence": 0.9, "sourceRef": "g:1", "rationale": "r", "verified": True},
            {"guard_id": "g2", "guard_type": "behavioral", "target_behavior": "b2", "confidence": 0.9, "sourceRef": "g:2", "rationale": "r", "verified": True},
        ],
        "no_oracle_risks": [
            {"risk_id": "n1", "risk_type": "low", "severity": "low", "confidence": 0.9, "sourceRef": "n:1", "rationale": "r", "mitigated": True},
            {"risk_id": "n2", "risk_type": "low", "severity": "low", "confidence": 0.9, "sourceRef": "n:2", "rationale": "r", "mitigated": True},
        ],
        "test_sources": [{"test_id": "missing-ref", "target_risk": "r3", "severity": "low", "sourceRef": "", "text": "assert x == y"}],
        "oracle_taxonomy_available": True,
        "semantic_guard_available": True,
        "critical_risk_coverage_available": True,
        "confidence": 0.9,
        "limits": {
            "confidence_threshold": 0.7,
            "max_oracle_classes": 1,
            "max_semantic_guards": 1,
            "max_no_oracle_risks": 1,
        },
    })

    assert report["overall_status"] == "hold"
    assert "oracle_classification_duplicate_oracle_id" in _codes(report)
    assert "oracle_classification_source_ref_missing" in _codes(report)
    assert "oracle_classification_oracle_budget_exceeded" in _codes(report)
    assert "oracle_classification_guard_budget_exceeded" in _codes(report)
    assert "oracle_classification_no_oracle_risk_budget_exceeded" in _codes(report)


def test_oracle_classification_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["oracle-classification-report"] == "schemas/HATE/v1/oracle-classification-report.schema.json"
