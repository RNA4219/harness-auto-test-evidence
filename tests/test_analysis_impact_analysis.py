"""Tests for HATE-GAP-049 impact analysis evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from hate.analysis.impact_analysis import (
    build_impact_analysis_report,
    evaluate_impact_analysis_fixture,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "expansion" / "impact-analysis"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "impact-analysis-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "impact-analysis-report"
    assert report["overall_status"] in {"pass", "hold", "blocked"}
    assert report["readiness_effect"] in {"none", "hold", "blocked"}
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_canonical_gap_049_fixture_paths_exist() -> None:
    assert (FIXTURES / "dependency-impact-pass" / "fixture.json").is_file()
    assert (FIXTURES / "missing-dependency-source-hold" / "fixture.json").is_file()


def test_dependency_impact_pass_fixture_passes() -> None:
    result = evaluate_impact_analysis_fixture(_fixture("dependency-impact-pass"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "none"
    _assert_report_contract(result["report"])


def test_missing_dependency_source_fixture_holds() -> None:
    result = evaluate_impact_analysis_fixture(_fixture("missing-dependency-source-hold"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "impact_analysis_missing_dependency_source"
    assert result["readiness_effect"] == "hold"
    _assert_report_contract(result["report"])


def test_missing_ownership_source_holds() -> None:
    report = build_impact_analysis_report({
        "changed_refs": [{"path": "src/test.py", "change_type": "modified", "sourceRef": "c:1"}],
        "affected_tests": [{"test_id": "t1", "confidence": 0.9, "sourceRef": "t:1", "rationale": "r"}],
        "affected_requirements": [{"requirement_id": "r1", "confidence": 0.9, "sourceRef": "req:1", "rationale": "r"}],
        "dependency_sources_available": True,
        "ownership_sources_available": False,
        "history_sources_available": True,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "impact_analysis_missing_ownership_source" in _codes(report)


def test_missing_history_source_holds() -> None:
    report = build_impact_analysis_report({
        "changed_refs": [{"path": "src/test.py", "change_type": "modified", "sourceRef": "c:1"}],
        "affected_tests": [{"test_id": "t1", "confidence": 0.9, "sourceRef": "t:1", "rationale": "r"}],
        "affected_requirements": [{"requirement_id": "r1", "confidence": 0.9, "sourceRef": "req:1", "rationale": "r"}],
        "dependency_sources_available": True,
        "ownership_sources_available": True,
        "history_sources_available": False,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "impact_analysis_missing_history_source" in _codes(report)


def test_low_confidence_holds() -> None:
    report = build_impact_analysis_report({
        "changed_refs": [{"path": "src/test.py", "change_type": "modified", "sourceRef": "c:1"}],
        "affected_tests": [{"test_id": "t1", "confidence": 0.5, "sourceRef": "t:1", "rationale": "r"}],
        "affected_requirements": [{"requirement_id": "r1", "confidence": 0.5, "sourceRef": "req:1", "rationale": "r"}],
        "dependency_sources_available": True,
        "ownership_sources_available": True,
        "history_sources_available": True,
        "confidence": 0.5,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "impact_analysis_confidence_missing" in _codes(report)


def test_affected_test_without_source_ref_holds() -> None:
    report = build_impact_analysis_report({
        "changed_refs": [{"path": "src/test.py", "change_type": "modified", "sourceRef": "c:1"}],
        "affected_tests": [{"test_id": "t1", "confidence": 0.9, "sourceRef": "", "rationale": "r"}],
        "affected_requirements": [{"requirement_id": "r1", "confidence": 0.9, "sourceRef": "req:1", "rationale": "r"}],
        "dependency_sources_available": True,
        "ownership_sources_available": True,
        "history_sources_available": True,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "impact_analysis_affected_test_without_source_ref" in _codes(report)


def test_affected_requirement_without_source_ref_holds() -> None:
    report = build_impact_analysis_report({
        "changed_refs": [{"path": "src/test.py", "change_type": "modified", "sourceRef": "c:1"}],
        "affected_tests": [{"test_id": "t1", "confidence": 0.9, "sourceRef": "t:1", "rationale": "r"}],
        "affected_requirements": [{"requirement_id": "r1", "confidence": 0.9, "sourceRef": "", "rationale": "r"}],
        "dependency_sources_available": True,
        "ownership_sources_available": True,
        "history_sources_available": True,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "impact_analysis_affected_requirement_without_source_ref" in _codes(report)


def test_impact_analysis_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["impact-analysis-report"] == "schemas/HATE/v1/impact-analysis-report.schema.json"