"""Tests for HATE-GAP-053 evidence synthesis evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from hate.analysis.evidence_synthesis import (
    build_evidence_synthesis_report,
    evaluate_evidence_synthesis_fixture,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "expansion" / "evidence-synthesis"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "evidence-synthesis-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "evidence-synthesis-report"
    assert report["overall_status"] in {"pass", "hold", "blocked"}
    assert report["readiness_effect"] in {"none", "hold", "blocked"}
    assert "requirement_synthesis" in report
    assert "evidence_synthesis_diagnostics" in report
    assert {
        "target_requirement_count",
        "weak_requirement_count",
        "unsatisfied_contract_count",
        "survived_mutation_count",
        "synthesized_confidence",
    } <= set(report["summary"])
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_canonical_gap_053_fixture_paths_exist() -> None:
    assert (FIXTURES / "contract-mutation-confidence-pass" / "fixture.json").is_file()
    assert (FIXTURES / "weak-evidence-inflation-denied" / "fixture.json").is_file()


def test_contract_mutation_confidence_fixture_passes() -> None:
    result = evaluate_evidence_synthesis_fixture(_fixture("contract-mutation-confidence-pass"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "none"
    _assert_report_contract(result["report"])


def test_weak_evidence_inflation_fixture_holds() -> None:
    result = evaluate_evidence_synthesis_fixture(_fixture("weak-evidence-inflation-denied"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "evidence_synthesis_weak_evidence_inflation_denied"
    assert result["readiness_effect"] == "hold"
    _assert_report_contract(result["report"])


def test_mutation_coverage_missing_holds() -> None:
    report = build_evidence_synthesis_report({
        "evidence_sources": [{"source_id": "es1", "source_type": "mutation", "target_requirement": "r1", "confidence": 0.9, "sourceRef": "es:1", "rationale": "r", "verified": True}],
        "mutation_coverage": [{"mutation_id": "mc1", "mutation_type": "operator", "killed": True, "confidence": 0.9, "sourceRef": "mc:1", "rationale": "r"}],
        "contract_coverage": [{"contract_id": "cc1", "contract_type": "postcondition", "satisfied": True, "confidence": 0.9, "sourceRef": "cc:1", "rationale": "r"}],
        "mutation_evidence_available": False,
        "contract_evidence_available": True,
        "strong_evidence_threshold": 0.8,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "evidence_synthesis_mutation_coverage_missing" in _codes(report)


def test_evidence_availability_defaults_to_hold() -> None:
    report = build_evidence_synthesis_report({
        "evidence_sources": [{"source_id": "es1", "source_type": "mutation", "target_requirement": "r1", "confidence": 0.9, "sourceRef": "es:1", "rationale": "r", "verified": True}],
        "mutation_coverage": [{"mutation_id": "mc1", "mutation_type": "operator", "killed": True, "confidence": 0.9, "sourceRef": "mc:1", "rationale": "r"}],
        "contract_coverage": [{"contract_id": "cc1", "contract_type": "postcondition", "satisfied": True, "confidence": 0.9, "sourceRef": "cc:1", "rationale": "r"}],
        "strong_evidence_threshold": 0.8,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert {
        "evidence_synthesis_mutation_coverage_missing",
        "evidence_synthesis_contract_coverage_missing",
    }.issubset(set(_codes(report)))


def test_contract_coverage_missing_holds() -> None:
    report = build_evidence_synthesis_report({
        "evidence_sources": [{"source_id": "es1", "source_type": "contract", "target_requirement": "r1", "confidence": 0.9, "sourceRef": "es:1", "rationale": "r", "verified": True}],
        "mutation_coverage": [{"mutation_id": "mc1", "mutation_type": "operator", "killed": True, "confidence": 0.9, "sourceRef": "mc:1", "rationale": "r"}],
        "contract_coverage": [{"contract_id": "cc1", "contract_type": "postcondition", "satisfied": True, "confidence": 0.9, "sourceRef": "cc:1", "rationale": "r"}],
        "mutation_evidence_available": True,
        "contract_evidence_available": False,
        "strong_evidence_threshold": 0.8,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "evidence_synthesis_contract_coverage_missing" in _codes(report)


def test_evidence_source_without_source_ref_holds() -> None:
    report = build_evidence_synthesis_report({
        "evidence_sources": [{"source_id": "es1", "source_type": "mutation", "target_requirement": "r1", "confidence": 0.9, "sourceRef": "", "rationale": "r", "verified": True}],
        "mutation_coverage": [{"mutation_id": "mc1", "mutation_type": "operator", "killed": True, "confidence": 0.9, "sourceRef": "mc:1", "rationale": "r"}],
        "contract_coverage": [{"contract_id": "cc1", "contract_type": "postcondition", "satisfied": True, "confidence": 0.9, "sourceRef": "cc:1", "rationale": "r"}],
        "mutation_evidence_available": True,
        "contract_evidence_available": True,
        "strong_evidence_threshold": 0.8,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "evidence_synthesis_source_ref_missing" in _codes(report)


def test_mutation_without_source_ref_holds() -> None:
    report = build_evidence_synthesis_report({
        "evidence_sources": [{"source_id": "es1", "source_type": "mutation", "target_requirement": "r1", "confidence": 0.9, "sourceRef": "es:1", "rationale": "r", "verified": True}],
        "mutation_coverage": [{"mutation_id": "mc1", "mutation_type": "operator", "killed": True, "confidence": 0.9, "sourceRef": "", "rationale": "r"}],
        "contract_coverage": [{"contract_id": "cc1", "contract_type": "postcondition", "satisfied": True, "confidence": 0.9, "sourceRef": "cc:1", "rationale": "r"}],
        "mutation_evidence_available": True,
        "contract_evidence_available": True,
        "strong_evidence_threshold": 0.8,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "evidence_synthesis_mutation_coverage_missing" in _codes(report)


def test_contract_without_source_ref_holds() -> None:
    report = build_evidence_synthesis_report({
        "evidence_sources": [{"source_id": "es1", "source_type": "contract", "target_requirement": "r1", "confidence": 0.9, "sourceRef": "es:1", "rationale": "r", "verified": True}],
        "mutation_coverage": [{"mutation_id": "mc1", "mutation_type": "operator", "killed": True, "confidence": 0.9, "sourceRef": "mc:1", "rationale": "r"}],
        "contract_coverage": [{"contract_id": "cc1", "contract_type": "postcondition", "satisfied": True, "confidence": 0.9, "sourceRef": "", "rationale": "r"}],
        "mutation_evidence_available": True,
        "contract_evidence_available": True,
        "strong_evidence_threshold": 0.8,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "evidence_synthesis_contract_coverage_missing" in _codes(report)


def test_requirement_level_weak_synthesis_holds() -> None:
    report = build_evidence_synthesis_report({
        "evidence_sources": [
            {
                "source_id": "es1",
                "source_type": "coverage",
                "target_requirement": "REQ-weak",
                "confidence": 0.55,
                "sourceRef": "es:1",
                "rationale": "Coverage only",
                "verified": True,
            }
        ],
        "mutation_coverage": [{"mutation_id": "mc1", "mutation_type": "operator", "killed": True, "confidence": 0.9, "sourceRef": "mc:1", "rationale": "r"}],
        "contract_coverage": [{"contract_id": "cc1", "contract_type": "postcondition", "satisfied": True, "confidence": 0.9, "sourceRef": "cc:1", "rationale": "r"}],
        "mutation_evidence_available": True,
        "contract_evidence_available": True,
        "strong_evidence_threshold": 0.8,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "evidence_synthesis_requirement_confidence_below_threshold" in _codes(report)
    assert report["summary"]["weak_requirement_count"] == 1
    assert "REQ-weak" in report["requirement_synthesis"]


def test_survived_mutation_and_unsatisfied_contract_hold() -> None:
    report = build_evidence_synthesis_report({
        "evidence_sources": [
            {"source_id": "es1", "source_type": "mutation", "target_requirement": "REQ-1", "confidence": 0.95, "sourceRef": "es:1", "rationale": "r", "verified": True},
            {"source_id": "es2", "source_type": "contract", "target_requirement": "REQ-1", "confidence": 0.95, "sourceRef": "es:2", "rationale": "r", "verified": True},
        ],
        "mutation_coverage": [{"mutation_id": "mc-survived", "mutation_type": "operator", "killed": False, "confidence": 0.95, "sourceRef": "mc:1", "rationale": "r"}],
        "contract_coverage": [{"contract_id": "cc-unsatisfied", "contract_type": "postcondition", "satisfied": False, "confidence": 0.95, "sourceRef": "cc:1", "rationale": "r"}],
        "mutation_evidence_available": True,
        "contract_evidence_available": True,
        "strong_evidence_threshold": 0.8,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "evidence_synthesis_survived_mutation_hold" in _codes(report)
    assert "evidence_synthesis_unsatisfied_contract_hold" in _codes(report)
    assert report["summary"]["survived_mutation_count"] == 1
    assert report["summary"]["unsatisfied_contract_count"] == 1


def test_unverified_strong_source_holds() -> None:
    report = build_evidence_synthesis_report({
        "evidence_sources": [{"source_id": "es-strong", "source_type": "contract", "target_requirement": "REQ-1", "confidence": 0.95, "sourceRef": "es:1", "rationale": "r", "verified": False}],
        "mutation_coverage": [{"mutation_id": "mc1", "mutation_type": "operator", "killed": True, "confidence": 0.95, "sourceRef": "mc:1", "rationale": "r"}],
        "contract_coverage": [{"contract_id": "cc1", "contract_type": "postcondition", "satisfied": True, "confidence": 0.95, "sourceRef": "cc:1", "rationale": "r"}],
        "mutation_evidence_available": True,
        "contract_evidence_available": True,
        "strong_evidence_threshold": 0.8,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "evidence_synthesis_unverified_strong_source_hold" in _codes(report)


def test_synthesis_budget_excess_holds() -> None:
    report = build_evidence_synthesis_report({
        "evidence_sources": [
            {"source_id": "es1", "source_type": "mutation", "target_requirement": "REQ-1", "confidence": 0.95, "sourceRef": "es:1", "rationale": "r", "verified": True},
            {"source_id": "es2", "source_type": "contract", "target_requirement": "REQ-1", "confidence": 0.95, "sourceRef": "es:2", "rationale": "r", "verified": True},
        ],
        "mutation_coverage": [
            {"mutation_id": "mc1", "mutation_type": "operator", "killed": True, "confidence": 0.95, "sourceRef": "mc:1", "rationale": "r"},
            {"mutation_id": "mc2", "mutation_type": "operator", "killed": True, "confidence": 0.95, "sourceRef": "mc:2", "rationale": "r"},
        ],
        "contract_coverage": [
            {"contract_id": "cc1", "contract_type": "postcondition", "satisfied": True, "confidence": 0.95, "sourceRef": "cc:1", "rationale": "r"},
            {"contract_id": "cc2", "contract_type": "postcondition", "satisfied": True, "confidence": 0.95, "sourceRef": "cc:2", "rationale": "r"},
        ],
        "mutation_evidence_available": True,
        "contract_evidence_available": True,
        "strong_evidence_threshold": 0.8,
        "confidence": 0.9,
        "limits": {
            "confidence_threshold": 0.7,
            "max_evidence_sources": 1,
            "max_mutation_coverage": 1,
            "max_contract_coverage": 1,
        },
    })

    assert report["overall_status"] == "hold"
    assert "evidence_synthesis_source_budget_exceeded" in _codes(report)
    assert "evidence_synthesis_mutation_budget_exceeded" in _codes(report)
    assert "evidence_synthesis_contract_budget_exceeded" in _codes(report)


def test_evidence_synthesis_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["evidence-synthesis-report"] == "schemas/HATE/v1/evidence-synthesis-report.schema.json"
