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
    assert "derived_affected_tests" in report
    assert "derived_affected_requirements" in report
    assert "impact_analysis_diagnostics" in report
    assert {
        "derived_test_count",
        "derived_requirement_count",
        "owner_count",
        "unmapped_changed_ref_count",
    } <= set(report["summary"])
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


def test_missing_source_availability_defaults_to_hold() -> None:
    report = build_impact_analysis_report({
        "changed_refs": [{"path": "src/test.py", "change_type": "modified", "sourceRef": "c:1"}],
        "affected_tests": [{"test_id": "t1", "confidence": 0.9, "sourceRef": "t:1", "rationale": "r"}],
        "affected_requirements": [{"requirement_id": "r1", "confidence": 0.9, "sourceRef": "req:1", "rationale": "r"}],
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert {
        "impact_analysis_missing_dependency_source",
        "impact_analysis_missing_ownership_source",
        "impact_analysis_missing_history_source",
    }.issubset(set(_codes(report)))


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


def test_derived_impacts_from_maps_are_reported() -> None:
    report = build_impact_analysis_report({
        "changed_refs": [{"path": "src/hate/foo.py", "change_type": "modified", "sourceRef": "c:1"}],
        "affected_tests": [],
        "affected_requirements": [],
        "dependency_graph": {"src/hate/foo.py": ["test_foo_unit"]},
        "history_index": {"src/hate/foo.py": ["test_foo_regression"]},
        "requirement_map": {"src/hate/foo.py": ["REQ-FOO"]},
        "ownership_map": {"src/hate": ["Team Core"]},
        "dependency_sources_available": True,
        "ownership_sources_available": True,
        "history_sources_available": True,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "pass"
    assert {item["test_id"] for item in report["derived_affected_tests"]} == {"test_foo_unit", "test_foo_regression"}
    assert report["derived_affected_requirements"][0]["requirement_id"] == "REQ-FOO"
    assert report["impact_analysis_diagnostics"]["owners"] == ["Team Core"]


def test_unmapped_changed_ref_and_missing_source_ref_hold() -> None:
    report = build_impact_analysis_report({
        "changed_refs": [{"path": "src/hate/unmapped.py", "change_type": "modified", "sourceRef": ""}],
        "affected_tests": [],
        "affected_requirements": [],
        "dependency_graph": {},
        "history_index": {},
        "requirement_map": {},
        "ownership_map": {},
        "dependency_sources_available": True,
        "ownership_sources_available": True,
        "history_sources_available": True,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "impact_analysis_changed_ref_without_source_ref" in _codes(report)
    assert "impact_analysis_unmapped_changed_ref" in _codes(report)
    assert report["summary"]["unmapped_changed_ref_count"] == 1


def test_impact_budget_excess_holds() -> None:
    report = build_impact_analysis_report({
        "changed_refs": [
            {"path": "src/a.py", "change_type": "modified", "sourceRef": "c:1"},
            {"path": "src/b.py", "change_type": "modified", "sourceRef": "c:2"},
        ],
        "affected_tests": [{"test_id": "explicit", "confidence": 0.9, "sourceRef": "t:0", "rationale": "r"}],
        "affected_requirements": [{"requirement_id": "REQ-0", "confidence": 0.9, "sourceRef": "r:0", "rationale": "r"}],
        "dependency_graph": {"src/a.py": ["test_a"], "src/b.py": ["test_b"]},
        "requirement_map": {"src/a.py": ["REQ-A"], "src/b.py": ["REQ-B"]},
        "history_index": {},
        "ownership_map": {"src": ["Team"]},
        "dependency_sources_available": True,
        "ownership_sources_available": True,
        "history_sources_available": True,
        "confidence": 0.9,
        "limits": {
            "confidence_threshold": 0.7,
            "max_changed_refs": 1,
            "max_affected_tests": 1,
            "max_affected_requirements": 1,
        },
    })

    assert report["overall_status"] == "hold"
    assert "impact_analysis_changed_ref_budget_exceeded" in _codes(report)
    assert "impact_analysis_affected_test_budget_exceeded" in _codes(report)
    assert "impact_analysis_affected_requirement_budget_exceeded" in _codes(report)


def test_impact_analysis_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["impact-analysis-report"] == "schemas/HATE/v1/impact-analysis-report.schema.json"
